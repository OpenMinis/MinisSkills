import CoreBluetooth
import Foundation

private func log(_ message: String) {
    print(message)
    fflush(stdout)
}

private enum Command: UInt8 {
    case requestBlockSize = 1
    case requestScreenSize = 2
    case requestStartTransfer = 3
    case dataAck = 5
}

private enum Status: UInt8 {
    case success = 0
    case transferEnd = 8
}

private enum Profile {
    case standard
    case compressed
}

private let serviceUUIDs = [
    CBUUID(string: "0000FEF0-0000-1000-8000-00805F9B34FB"),
    CBUUID(string: "0000FDF0-0000-1000-8000-00805F9B34FB")
]
private let controlCharacteristicUUIDs = [
    CBUUID(string: "0000FEF1-0000-1000-8000-00805F9B34FB"),
    CBUUID(string: "0000FDF1-0000-1000-8000-00805F9B34FB")
]
private let dataCharacteristicUUIDs = [
    CBUUID(string: "0000FEF2-0000-1000-8000-00805F9B34FB"),
    CBUUID(string: "0000FDF2-0000-1000-8000-00805F9B34FB")
]

private final class MacImageTransfer: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private lazy var central = CBCentralManager(delegate: self, queue: queue)
    private let queue = DispatchQueue(label: "com.todoocard.mac-image-transfer")
    private let payloadURL: URL
    private let profile: Profile
    private let targetName: String?
    private let targetID: UUID?
    private let listOnly: Bool
    private let probeOnly: Bool
    private let allowDeviceButton: Bool
    private var seenIDs = Set<UUID>()
    private var payload = Data()
    private var peripheral: CBPeripheral?
    private var controlCharacteristic: CBCharacteristic?
    private var dataCharacteristic: CBCharacteristic?
    private var blockPayloadSize = 0
    private var nextCompressedBlockIndex: Int?
    private var lastProgress = -1
    private var finalAckTimer: DispatchSourceTimer?
    private var controlResponseTimer: DispatchSourceTimer?
    private var lastControlCommand: UInt8?
    private var retriedControlWithoutResponse = false
    private var sessionStarted = false

    init(payloadURL: URL, profile: Profile, targetName: String?, targetID: UUID?, listOnly: Bool, probeOnly: Bool, allowDeviceButton: Bool) {
        self.payloadURL = payloadURL
        self.profile = profile
        self.targetName = targetName
        self.targetID = targetID
        self.listOnly = listOnly
        self.probeOnly = probeOnly
        self.allowDeviceButton = allowDeviceButton
        super.init()
    }

    func run() {
        if !listOnly, !probeOnly {
            do {
                payload = try Data(contentsOf: payloadURL)
            } catch {
                log("Failed to read payload: \(error)")
                Foundation.exit(2)
            }
            log("Payload: \(payloadURL.path)")
            log("Size: \(payload.count) bytes")
            log("Profile: \(profile == .compressed ? "compressed T3" : "standard")")
        }
        _ = central
        dispatchMain()
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else {
            log("Bluetooth state: \(central.state.rawValue)")
            return
        }
        if listOnly {
            log("Scanning nearby BLE devices for 30s ...")
            queue.asyncAfter(deadline: .now() + .seconds(30)) { Foundation.exit(0) }
        } else if probeOnly {
            log("Scanning for probe target ...")
        } else {
            log("Scanning for image-transfer device ...")
        }
        if !listOnly {
            queue.asyncAfter(deadline: .now() + .seconds(45)) { [weak self] in
                guard let self, self.peripheral == nil else { return }
                log("Timed out scanning for target")
                Foundation.exit(14)
            }
        }
        central.scanForPeripherals(withServices: nil, options: [
            CBCentralManagerScanOptionAllowDuplicatesKey: true
        ])
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let advertisedName = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = advertisedName ?? peripheral.name ?? ""
        if listOnly {
            guard !seenIDs.contains(peripheral.identifier) else { return }
            seenIDs.insert(peripheral.identifier)
            let services = (advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID])?
                .map(\.uuidString)
                .joined(separator: ",") ?? ""
            log("BLE \(name.isEmpty ? "(no name)" : name) id=\(peripheral.identifier) RSSI=\(RSSI) services=\(services)")
            return
        }

        if let targetID, peripheral.identifier != targetID { return }
        if let targetName, !name.localizedCaseInsensitiveContains(targetName) { return }
        if targetID == nil, targetName == nil {
            let advertisedServices = advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] ?? []
            let lowered = name.lowercased()
            let hasImageService = advertisedServices.contains { serviceUUIDs.contains($0) }
            guard hasImageService || lowered.contains("todoocard") || lowered.contains("potatocard") || lowered.hasPrefix("nemr") else { return }
        }

        log("Found \(name.isEmpty ? peripheral.identifier.uuidString : name) id=\(peripheral.identifier) RSSI=\(RSSI)")
        self.peripheral = peripheral
        central.stopScan()
        peripheral.delegate = self
        central.connect(peripheral, options: nil)
        queue.asyncAfter(deadline: .now() + .seconds(15)) { [weak self, weak peripheral] in
            guard let self, let peripheral, self.peripheral === peripheral, peripheral.state != .connected else { return }
            log("Timed out connecting")
            Foundation.exit(15)
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        log("Connected")
        peripheral.discoverServices(probeOnly ? nil : serviceUUIDs)
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        log("Connect failed: \(error?.localizedDescription ?? "unknown")")
        Foundation.exit(3)
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        log("Disconnected: \(error?.localizedDescription ?? "no error")")
        // Never resume a partial indexed frame; retry from block zero.
        if !listOnly && !probeOnly {
            log("Transfer aborted; full-frame retry required")
            Foundation.exit(18)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error {
            log("Discover services failed: \(error)")
            Foundation.exit(4)
        }
        guard let services = peripheral.services, !services.isEmpty else {
            log("Image-transfer service not found")
            Foundation.exit(5)
        }
        services.forEach { peripheral.discoverCharacteristics(nil, for: $0) }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error {
            log("Discover characteristics failed: \(error)")
            Foundation.exit(6)
        }
        service.characteristics?.forEach { characteristic in
            if probeOnly {
                log("Characteristic service=\(service.uuid.uuidString) uuid=\(characteristic.uuid.uuidString) props=\(Self.propertiesDescription(characteristic.properties))")
            }
            if controlCharacteristicUUIDs.contains(characteristic.uuid) {
                controlCharacteristic = characteristic
                if characteristic.properties.contains(.notify) || characteristic.properties.contains(.indicate) {
                    peripheral.setNotifyValue(true, for: characteristic)
                }
            } else if dataCharacteristicUUIDs.contains(characteristic.uuid) {
                dataCharacteristic = characteristic
            }
        }
        if probeOnly, service == peripheral.services?.last {
            Foundation.exit(0)
        }
        beginIfReady()
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if let error {
            log("Enable notify failed: \(error)")
            Foundation.exit(7)
        }
        beginIfReady()
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error {
            log("Notification failed: \(error)")
            Foundation.exit(8)
        }
        guard let data = characteristic.value else { return }
        handleControlMessage(data)
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error {
            log("Write failed for \(characteristic.uuid.uuidString): \(error)")
            Foundation.exit(17)
        }
        log("Write ok for \(characteristic.uuid.uuidString)")
    }

    func peripheralIsReady(toSendWriteWithoutResponse peripheral: CBPeripheral) {
        if profile == .compressed {
            pumpCompressed()
        }
    }

    private func beginIfReady() {
        guard peripheral != nil, let controlCharacteristic, dataCharacteristic != nil else { return }
        let waits = controlCharacteristic.properties.contains(.notify) || controlCharacteristic.properties.contains(.indicate)
        guard !waits || controlCharacteristic.isNotifying else { return }
        guard !sessionStarted else { return }
        sessionStarted = true
        log("Characteristics ready: control=\(controlCharacteristic.uuid.uuidString), data=\(dataCharacteristic?.uuid.uuidString ?? "")")
        log("Control props: \(Self.propertiesDescription(controlCharacteristic.properties))")
        if let dataCharacteristic {
            log("Data props: \(Self.propertiesDescription(dataCharacteristic.properties))")
        }
        writeCommand(Data([Command.requestBlockSize.rawValue]))
    }

    private func writeCommand(_ data: Data) {
        guard let peripheral, let controlCharacteristic else { return }
        let type: CBCharacteristicWriteType = controlCharacteristic.properties.contains(.write) ? .withResponse : .withoutResponse
        lastControlCommand = data.first
        startControlResponseTimer(command: data.first, originalData: data, writeType: type)
        log("Control -> \(data.map { String(format: "%02x", $0) }.joined(separator: " "))")
        peripheral.writeValue(data, for: controlCharacteristic, type: type)
    }

    private func handleControlMessage(_ data: Data) {
        let bytes = [UInt8](data)
        guard let first = bytes.first, let command = Command(rawValue: first) else {
            log("Control <- \(bytes.map { String(format: "%02x", $0) }.joined(separator: " "))")
            return
        }
        controlResponseTimer?.cancel()
        controlResponseTimer = nil
        retriedControlWithoutResponse = false
        log("Control <- \(bytes.map { String(format: "%02x", $0) }.joined(separator: " "))")
        switch command {
        case .requestBlockSize:
            guard bytes.count >= 3, bytes[2] == Status.success.rawValue else {
                log("Block size rejected")
                Foundation.exit(9)
            }
            blockPayloadSize = max(0, Int(bytes[1]) - 4)
            log("Block payload size: \(blockPayloadSize)")
            requestScreenSize()
        case .requestScreenSize:
            guard bytes.count >= 2, bytes[1] == Status.success.rawValue else {
                log("Payload length rejected")
                Foundation.exit(10)
            }
            writeCommand(Data([Command.requestStartTransfer.rawValue]))
        case .dataAck:
            guard bytes.count >= 2 else { return }
            if bytes[1] == Status.transferEnd.rawValue {
                finalAckTimer?.cancel()
                log("Transfer completed and refresh acknowledged")
                Foundation.exit(0)
            }
            guard bytes[1] == Status.success.rawValue, bytes.count >= 6 else {
                log("Data block rejected")
                Foundation.exit(11)
            }
            let index = Int(bytes[2]) | Int(bytes[3]) << 8 | Int(bytes[4]) << 16 | Int(bytes[5]) << 24
            if profile == .compressed {
                nextCompressedBlockIndex = index
                pumpCompressed()
            } else {
                sendStandardBlock(index)
            }
        default:
            break
        }
    }

    private func requestScreenSize() {
        var data = Data([Command.requestScreenSize.rawValue])
        data.append(UInt8(payload.count & 0xff))
        data.append(UInt8((payload.count >> 8) & 0xff))
        data.append(UInt8((payload.count >> 16) & 0xff))
        data.append(UInt8((payload.count >> 24) & 0xff))
        var flags: UInt8 = profile == .compressed ? 0x01 : 0x03
        if allowDeviceButton { flags |= 0x10 }
        data.append(flags)
        writeCommand(data)
    }

    private func makeBlock(index: Int) -> (packet: Data, percent: Int, isLast: Bool)? {
        guard blockPayloadSize > 0 else { return nil }
        let offset = index * blockPayloadSize
        guard offset < payload.count else { return nil }
        let length = min(blockPayloadSize, payload.count - offset)
        var packet = Data()
        packet.append(UInt8(index & 0xff))
        packet.append(UInt8((index >> 8) & 0xff))
        packet.append(UInt8((index >> 16) & 0xff))
        packet.append(UInt8((index >> 24) & 0xff))
        packet.append(payload.subdata(in: offset ..< offset + length))
        let written = offset + length
        return (packet, Int(Double(written) / Double(payload.count) * 100), written >= payload.count)
    }

    private func sendStandardBlock(_ index: Int) {
        guard let peripheral, let dataCharacteristic, let block = makeBlock(index: index) else { return }
        let type: CBCharacteristicWriteType = dataCharacteristic.properties.contains(.writeWithoutResponse) ? .withoutResponse : .withResponse
        peripheral.writeValue(block.packet, for: dataCharacteristic, type: type)
        emitProgress(block.percent, index: index)
        if block.isLast {
            waitForFinalAck(seconds: 5)
        }
    }

    private func pumpCompressed() {
        guard let peripheral, let dataCharacteristic else { return }
        guard dataCharacteristic.properties.contains(.writeWithoutResponse) else {
            log("Compressed transfer requires writeWithoutResponse data characteristic")
            Foundation.exit(12)
        }
        while peripheral.canSendWriteWithoutResponse {
            guard let index = nextCompressedBlockIndex, let block = makeBlock(index: index) else { return }
            peripheral.writeValue(block.packet, for: dataCharacteristic, type: .withoutResponse)
            emitProgress(block.percent, index: index)
            if block.isLast {
                nextCompressedBlockIndex = nil
                log("Payload written; waiting for refresh ack")
                waitForFinalAck(seconds: 90)
                return
            }
            nextCompressedBlockIndex = index + 1
        }
        queue.asyncAfter(deadline: .now() + .milliseconds(6)) { [weak self] in
            self?.pumpCompressed()
        }
    }

    private func emitProgress(_ percent: Int, index: Int) {
        guard percent != lastProgress, percent.isMultiple(of: 5) || percent >= 100 else { return }
        lastProgress = percent
        log("Progress: \(percent)% block=\(index)")
    }

    private func waitForFinalAck(seconds: Int) {
        finalAckTimer?.cancel()
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + .seconds(seconds))
        timer.setEventHandler {
            log("Timed out waiting for final refresh ack")
            Foundation.exit(13)
        }
        finalAckTimer = timer
        timer.resume()
    }

    private func startControlResponseTimer(command: UInt8?, originalData: Data, writeType: CBCharacteristicWriteType) {
        controlResponseTimer?.cancel()
        guard command != nil else { return }
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + .seconds(5))
        timer.setEventHandler { [weak self] in
            guard let self else { return }
            if writeType == .withResponse,
               !self.retriedControlWithoutResponse,
               let peripheral = self.peripheral,
               let controlCharacteristic = self.controlCharacteristic,
               controlCharacteristic.properties.contains(.writeWithoutResponse) {
                self.retriedControlWithoutResponse = true
                log("Control response timed out; retrying withoutResponse")
                peripheral.writeValue(originalData, for: controlCharacteristic, type: .withoutResponse)
                self.startControlResponseTimer(command: command, originalData: originalData, writeType: .withoutResponse)
                return
            }
            log("Control response timed out")
            Foundation.exit(16)
        }
        controlResponseTimer = timer
        timer.resume()
    }

    private static func propertiesDescription(_ properties: CBCharacteristicProperties) -> String {
        var values: [String] = []
        if properties.contains(.broadcast) { values.append("broadcast") }
        if properties.contains(.read) { values.append("read") }
        if properties.contains(.writeWithoutResponse) { values.append("writeWithoutResponse") }
        if properties.contains(.write) { values.append("write") }
        if properties.contains(.notify) { values.append("notify") }
        if properties.contains(.indicate) { values.append("indicate") }
        return values.joined(separator: ",")
    }
}

private func usage() -> Never {
    log("""
    Usage:
      MacImageTransfer --list
      MacImageTransfer --probe [--name TodooCard] [--id UUID]
      MacImageTransfer --payload /path/final-180.protocol.qlz --compressed [--name TodooCard] [--id UUID]
      MacImageTransfer --payload /path/file.bin --standard [--name PotatoCard] [--id UUID]
    """)
    Foundation.exit(64)
}

private var payloadPath: String?
private var profile: Profile = .compressed
private var targetName: String?
private var targetID: UUID?
private var listOnly = false
private var probeOnly = false
private var allowDeviceButton = false
private var args = Array(CommandLine.arguments.dropFirst())
while !args.isEmpty {
    let arg = args.removeFirst()
    switch arg {
    case "--list":
        listOnly = true
    case "--probe":
        probeOnly = true
    case "--payload":
        guard !args.isEmpty else { usage() }
        payloadPath = args.removeFirst()
    case "--compressed":
        profile = .compressed
    case "--standard":
        profile = .standard
    case "--name":
        guard !args.isEmpty else { usage() }
        targetName = args.removeFirst()
    case "--id":
        guard !args.isEmpty, let uuid = UUID(uuidString: args.removeFirst()) else { usage() }
        targetID = uuid
    case "--allow-device-button":
        allowDeviceButton = true
    default:
        usage()
    }
}

let payloadURL = URL(fileURLWithPath: payloadPath ?? "/dev/null")
if !listOnly, !probeOnly, payloadPath == nil {
    usage()
}
MacImageTransfer(
    payloadURL: payloadURL,
    profile: profile,
    targetName: targetName,
    targetID: targetID,
    listOnly: listOnly,
    probeOnly: probeOnly,
    allowDeviceButton: allowDeviceButton
).run()
