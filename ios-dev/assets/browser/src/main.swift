import UIKit
import WebKit

final class BrowserViewController: UIViewController, WKNavigationDelegate, UITextFieldDelegate {
    private let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
    private let addressField = UITextField()
    private let backButton = UIButton(type: .system)
    private let forwardButton = UIButton(type: .system)
    private let reloadButton = UIButton(type: .system)
    private let progress = UIProgressView(progressViewStyle: .bar)
    private var observation: NSKeyValueObservation?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground

        addressField.borderStyle = .roundedRect
        addressField.placeholder = "输入网址或搜索"
        addressField.keyboardType = .webSearch
        addressField.autocapitalizationType = .none
        addressField.autocorrectionType = .no
        addressField.clearButtonMode = .whileEditing
        addressField.returnKeyType = .go
        addressField.delegate = self

        backButton.setImage(UIImage(systemName: "chevron.left"), for: .normal)
        forwardButton.setImage(UIImage(systemName: "chevron.right"), for: .normal)
        reloadButton.setImage(UIImage(systemName: "arrow.clockwise"), for: .normal)
        backButton.addTarget(self, action: #selector(goBack), for: .touchUpInside)
        forwardButton.addTarget(self, action: #selector(goForward), for: .touchUpInside)
        reloadButton.addTarget(self, action: #selector(reload), for: .touchUpInside)

        let bar = UIStackView(arrangedSubviews: [backButton, forwardButton, addressField, reloadButton])
        bar.axis = .horizontal
        bar.spacing = 8
        bar.alignment = .center

        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true

        for v in [bar, progress, webView] as [UIView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(v)
        }
        let g = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            bar.topAnchor.constraint(equalTo: g.topAnchor, constant: 6),
            bar.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 10),
            bar.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -10),
            bar.heightAnchor.constraint(equalToConstant: 40),
            backButton.widthAnchor.constraint(equalToConstant: 30),
            forwardButton.widthAnchor.constraint(equalToConstant: 30),
            reloadButton.widthAnchor.constraint(equalToConstant: 30),
            progress.topAnchor.constraint(equalTo: bar.bottomAnchor, constant: 4),
            progress.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            progress.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.topAnchor.constraint(equalTo: progress.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        observation = webView.observe(\.estimatedProgress, options: [.new]) { [weak self] wv, _ in
            guard let self else { return }
            self.progress.setProgress(Float(wv.estimatedProgress), animated: true)
            self.progress.isHidden = wv.estimatedProgress >= 1
        }
        load("https://www.apple.com")
        updateButtons()
    }

    private func load(_ input: String) {
        let text = input.trimmingCharacters(in: .whitespaces)
        var url: URL?
        if text.contains(".") && !text.contains(" ") {
            url = URL(string: text.hasPrefix("http") ? text : "https://" + text)
        }
        if url == nil {
            var c = URLComponents(string: "https://www.bing.com/search")!
            c.queryItems = [URLQueryItem(name: "q", value: text)]
            url = c.url
        }
        if let url { webView.load(URLRequest(url: url)) }
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        textField.resignFirstResponder()
        load(textField.text ?? "")
        return true
    }

    @objc private func goBack() { webView.goBack() }
    @objc private func goForward() { webView.goForward() }
    @objc private func reload() { webView.reload() }

    private func updateButtons() {
        backButton.isEnabled = webView.canGoBack
        forwardButton.isEnabled = webView.canGoForward
        addressField.text = webView.url?.absoluteString
    }

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) { updateButtons() }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        updateButtons()
        title = webView.title
    }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
        guard let ws = scene as? UIWindowScene else { return }
        let w = UIWindow(windowScene: ws)
        w.rootViewController = BrowserViewController()
        w.makeKeyAndVisible()
        window = w
    }
}

final class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let c = UISceneConfiguration(name: "Default", sessionRole: connectingSceneSession.role)
        c.delegateClass = SceneDelegate.self
        return c
    }
}

UIApplicationMain(CommandLine.argc, CommandLine.unsafeArgv, nil, NSStringFromClass(AppDelegate.self))
