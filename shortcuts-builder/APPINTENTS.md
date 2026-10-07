# AppIntents Reference

Catalog of first-party AppIntent actions for **iOS/iPadOS**. It started from the macOS ToolKit v63 catalog and backups; macOS-only entries (System Settings panes under `com.apple.systempreferences.*` and `com.apple.Desktop-Settings.*`) that are absent from the iOS 27 ToolKit snapshot were removed, since this skill targets iPhone/iPad by default. The full macOS catalog is kept outside the skill (see CHANGELOG, "iOS default").

OS 27 ToolKit v78 snapshots add more AppIntent, Siri intent, and flow-tool identifiers to the packaged validator allowlist. Those v78 identifiers are validation coverage only unless their schemas are documented here, in another reference file, or in a golden/exported XML sample.

The packaged `data/toolkit-v78-first-party-parameter-keys.json` file adds a broader **parameter-key coverage tier** for OS 27 exploration: 2,585 first-party `com.apple.*` and `is.workflow.actions.*` ToolKit rows from local macOS 27 and iOS 27 Simulator databases, with platform labels, Python names, tool types, parameter keys, localized parameter names, sort order, flags, boolean labels, type names, and per-parameter platform provenance. `data/toolkit-v78-first-party-enum-cases.json` adds concrete enum cases for the referenced action and automation-trigger parameter type names. Both files intentionally omit Apple descriptions and do not prove that an action is authoring-safe. `scripts/lookup_action_grounding.py` uses these snapshots as fallbacks when an action is allowlisted but absent from the curated Shortpy grounding catalog. It emits separate notes for action availability, OS 27-era parameter metadata, enum cases, one-sided action provenance, and target-filtered parameter summaries when individual fields exist only on macOS 27 or only in the iOS 27 Simulator ToolKit.

## AppIntents vs WF*Actions

| Aspect | WF*Actions | AppIntents |
|--------|-----------|------------|
| Identifier format | `is.workflow.actions.*` | Full ID (e.g., `com.apple.shortcuts.OpenShortcutsStaticDeepLinks`) |
| Origin | Legacy Shortcuts (pre-iOS 16) | App Intents framework (iOS 16+) |
| Invocation | Direct identifier in action | Direct identifier in `WFWorkflowActionIdentifier` (with AppIntentDescriptor) |
| Scope | Core shortcut actions | System integrations, deep links, app extensions |

## Platform Availability

**Platform support is not uniform.** The default target of this skill is iOS/iPadOS. An AppIntent that appears in this catalog may be:

- **Universal** — available on both iOS/iPadOS and macOS (most settings deep-links from apps that exist on both platforms).
- **macOS-only** — the ones that exist only on the Mac were removed from this file. If a request truly needs a Mac-only action, validate with `--target-platform macos` and say that the shortcut is Mac-only.
- **iOS-only** — deep-links that open destinations inside the iOS Shortcuts app, iOS Settings, or iOS-exclusive apps. These fail on macOS even if the XML validates.

**When a shortcut is intended to run on macOS, prefer the macOS-native equivalent or a universal Shortcuts action over a platform-specific AppIntent.** There is no compile-time check — the Shortcuts app accepts the plist on either platform and only reveals the mismatch at runtime.

### Known iOS-only AppIntents (non-exhaustive)

Do **not** use these when targeting macOS (the default target is iOS, so this is only a reminder):

| Identifier | Title | Notes |
|------------|-------|-------|
| `com.apple.shortcuts.OpenShortcutsStaticDeepLinks` | Open Shortcuts Settings | iOS-only — the Shortcuts app has no "Settings" pane on macOS. |

If you hit a runtime failure on macOS for an intent that validated cleanly, assume platform mismatch first. Add the failing identifier to the table above (with a short note) so the next build avoids it.

## OS 26 to 27 ToolKit Updates

The Automators OS 26 to 27 thread published a useful delta list on June 12-13, 2026. The identifiers below were cross-checked against local macOS 27 ToolKit v78 and, where noted, a hydrated iOS 27.0 Simulator ToolKit v78 database.

These entries document authoring metadata. They do not prove runtime availability on every platform; use the macOS/iOS notes when choosing actions.

| Display Name | Identifier | Source | Observed Parameters |
|--------------|------------|--------|---------------------|
| Set Battery Charge Limit | `com.apple.ShortcutsActions.SetBatteryChargeLimitAction` | macOS 27 v78 + iOS 27 Simulator v78 | `limit`, `setUntilTomorrow`; Automators reports this was added in OS 26.4. |
| Get Multitasking Mode | `com.apple.ShortcutsActions.GetMultitaskingModeAction` | macOS 27 v78 + iOS 27 Simulator v78 | none; Automators reports this was added in OS 26.4. |
| Set Multitasking Mode | `com.apple.ShortcutsActions.SetMultitaskingModeAction` | macOS 27 v78 + iOS 27 Simulator v78; exported Stage Manager automation sample | `mode`, `automaticallyShowAndHideDock`, `showRecentApps`; mode cases are `fullScreenApps`, `stageManager`, `windowedApps`. Apple may serialize `mode` as an AppEnum-style dictionary with `identifier`/`value` plus localized `title`/`subtitle`; accept that shape as well as a bare literal. |
| Share and Collaborate | `com.apple.sociallayerd.CollaborationIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `recipients` |
| Share | `com.apple.SharingUIService.ShareIntent` | iOS 27 Simulator v78 | `shareTransport`, `recipients`, `mode`, `content` |
| Create Note | `com.apple.mobilenotes.SharingExtension` | macOS 27 v78 | `name`, `contents`, `folder`, `interpretAsMarkdown`, `OpenWhenRun` |
| Create Tab Group | `com.apple.Safari.CreateNewTabGroup` / `com.apple.mobilesafari.CreateNewTabGroup` | macOS 27 v78 + iOS 27 Simulator v78 | `contents`, `name`; `contents` accepts URLs or Safari tab entities |
| Set Appearance on Apple TV | `com.apple.TVRemoteUIService.ToggleSystemAppearanceIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `device`, `appearanceToggle`, `ShowWhenRun`; `appearanceToggle` cases are `light` and `dark`. Renamed from **Set Light/Dark Mode**. |
| Open Inbox | `com.apple.MobileSMS.ChangeFilterModeIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `filterMode` |
| Delete Conversations | `com.apple.MobileSMS.DeleteConversationIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `entities` |
| Delete Messages | `com.apple.MobileSMS.DeleteMessageIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `entities`, `WFLinkMessagesEntityVariablePickerKey` |
| Mark as Read | `com.apple.MobileSMS.MarkConversationAsUnreadIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `operation`, `conversation`, `unreadState`, `OpenWhenRun` |
| Search in Messages | `com.apple.MobileSMS.SearchMessagesIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `criteria` |
| Send Tapback | `com.apple.MobileSMS.SendMessageReactionIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `message`, `reaction`, `WFLinkMessagesEntityVariablePickerKey`; `reaction` cases are `2000` Love, `2001` Like, `2002` Dislike, `2003` Laugh At, `2004` Emphasize, `2005` Question. |
| Find Message (Messages) | `com.apple.MobileSMS.MessageEntity` | macOS 27 v78 + iOS 27 Simulator v78 | `WFContentItemFilter`, `WFContentItemSortProperty`, `WFContentItemSortOrder`, `WFContentItemLimitEnabled`, `WFContentItemLimitNumber`, `WFCompoundType`, `WFContentItemInputParameter` |
| Find Album | `com.apple.Photos.AlbumEntity` / `com.apple.mobileslideshow.AlbumEntity` | macOS 27 v78 + iOS 27 Simulator v78 | `WFContentItemFilter`, `WFContentItemSortProperty`, `WFContentItemSortOrder`, `WFContentItemLimitEnabled`, `WFContentItemLimitNumber`, `WFCompoundType`, `WFContentItemInputParameter` |
| Search | `com.apple.Photos.PhotosSearchAssistantIntent` / `com.apple.mobileslideshow.PhotosSearchAssistantIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `criteria`; renamed from **Search Photos** in the Automators OS 26.4 delta. |
| Auto Enhance Photo | `com.apple.Photos.EnhanceIntent` / `com.apple.mobileslideshow.EnhanceIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `assets`, `enabled` |
| Favorite Photos | `com.apple.Photos.FavoriteAssetsIntent` / `com.apple.mobileslideshow.FavoriteAssetsIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `assets`, `action`; action cases are `favorite` and `unfavorite`. |
| Open Photo | `com.apple.Photos.OpenAssetIntent` / `com.apple.mobileslideshow.OpenAssetIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `target` |
| Hide Photos | `com.apple.Photos.HideAssetsIntent` / `com.apple.mobileslideshow.HideAssetsIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `assets`, `action`; action cases are `hide` and `unhide`. |
| Delete Albums | `com.apple.Photos.DeleteAlbumsIntent` / `com.apple.mobileslideshow.DeleteAlbumsIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `entities` |
| Delete Albums | `com.apple.Photos.PhotosDeleteAlbumsAssistantIntent` / `com.apple.mobileslideshow.PhotosDeleteAlbumsAssistantIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `entities` |
| Find Message (Mail) | `com.apple.mail.MailMessage` / `com.apple.mail.MailMessageEntity` | macOS 27 v78 | `WFContentItemFilter`, `WFContentItemSortProperty`, `WFContentItemSortOrder`, `WFContentItemLimitEnabled`, `WFContentItemLimitNumber`, `WFCompoundType`, `WFContentItemInputParameter` |
| Create Group | `com.apple.reminders.CreateGroupAppIntent` | macOS 27 v78 | `name`, `lists` |
| Create Section | `com.apple.reminders.CreateSectionAppIntent` | macOS 27 v78 | `list`, `name`, `OpenWhenRun` |
| Edit List | `com.apple.reminders.ListEntity-UpdatableEntity` | macOS 27 v78 | `badge`, `color`, `entity`, `parent` |
| Delete Lists | `com.apple.reminders.DeleteListsAppIntent` | macOS 27 v78 | `entities` |
| Delete Groups | `com.apple.reminders.DeleteRemindersListGroupsAppIntent` | macOS 27 v78 | `entities`, `deleteSublists` |
| Delete Sections | `com.apple.reminders.DeleteSectionsAppIntent` | macOS 27 v78 | `entities` |
| Set Switch Control | `com.apple.UniversalAccess.UASettingsShortcuts.UAToggleSwitchControlIntent` | macOS 27 v78 | `operation`, `state`, `ShowWhenRun` |
| Set Motion Cues | `com.apple.UniversalAccess.UASettingsShortcuts.UAToggleMotionCuesIntent` | macOS 27 v78 | `operation`, `state`, `ShowWhenRun` |
| Adjust Hearing Device Volume | `com.apple.HearingApp.AdjustVolumeIntent` | iOS 27 runtime metadata + Simulator v78 | `direction` (`VolumeDirection`: Increase/Decrease), `ear` (`HearingEarSelection`: Left/Right/Both) |
| Mute Hearing Device Volume | `com.apple.HearingApp.MuteVolumeIntent` | iOS 27 Simulator v78 | none |
| Select Hearing Device Preset | `com.apple.HearingApp.SelectPresetIntent` | iOS 27 runtime metadata + Simulator v78 | `presetName`, `ear` (`HearingEarSelection`: Left/Right/Both) |

Messages metadata notes: `Open Inbox` exposes `filterMode` as a numeric enum from the local ToolKit database; observed titles include **Unknown Senders**, **All Transactions**, **All Promotions**, **Spam**, **Recently Deleted**, **Unread**, and **Send Later**, but several numeric cases are all localized as **Messages**, so prefer exported samples before hard-coding those ambiguous values. `Mark as Read` uses `operation` cases `mark` / `toggle`, `unreadState` is a boolean rendered as **Unread** / **Read**, and `OpenWhenRun` is a standard boolean. `Find Message (Messages)` sort properties are `isRead`, `body`, `subject`, `date`, and `Random`; `WFCompoundType` uses `0` (**Any**) / `1` (**All**) and `WFContentItemInputParameter = Library` (**Message**). `Send Tapback` reaction values are documented in the table above.

Photos uses platform-specific AppIntent namespaces in v78: prefer `com.apple.Photos.*` on macOS and `com.apple.mobileslideshow.*` on iOS/iPadOS for the paired rows above. `Find Album` sort properties are `albumType`, `name`, `creationDate`, and `Random`; `WFCompoundType` uses `0` (**Any**) / `1` (**All**) and `WFContentItemInputParameter = Library` (**Album**). The Photos action enums currently exposed by ToolKit are simple literal values for `Favorite Photos` (`favorite` / `unfavorite`), `Hide Photos` (`hide` / `unhide`), and `Search` criteria as plain text; entity picker serialization for concrete albums/photos still needs exported samples.

Mail exposes both `com.apple.mail.MailMessage` and `com.apple.mail.MailMessageEntity` for **Find Message**. The older row sorts by `dateReceived` or `Random`; the entity row sorts by `subject`, `body`, `dateReceived`, `isRead`, or `Random`. Keep both as valid aliases until an exported shortcut shows one is deprecated.

Reminders metadata notes: `Edit List` in ToolKit v78 exposes only `badge`, `color`, `entity`, and `parent` as top-level parameters, even though the Automators row describes a broader set of editable properties such as Auto-Categorize, Pinned, List Layout, Name, Sharing Participants, Show Completed, Sorting Style, and Type. Do not invent those missing keys until an exported shortcut proves their plist shape. `Delete Groups` also exposes `deleteSublists` as a boolean.

### Linked OS 18 to 26.1 ToolKit Deltas

The earlier Automators iOS 18 to OS 26.1 thread includes additional rows that local ToolKit v78 can identify. These are covered by the packaged parameter and enum catalogs, but picker/entity values still require exported samples before hard-coding authoring templates.

| Display Name | Identifier | Source | Observed Parameters |
|--------------|------------|--------|---------------------|
| Add Alarm | `com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent` | macOS 27 v78 | `dateComponents`, `name`, `repeats`, `allowsSnooze`, `OpenWhenRun`; `repeats` cases are `sunday` through `saturday`. |
| Create List | `com.apple.reminders.TTRCreateListAppIntent` | macOS 27 v78 | `name`, `type`, `group`, `OpenWhenRun`; `type` cases are `standard` and `groceries`. |
| Open Person | `com.apple.Photos.OpenPersonIntent` / `com.apple.mobileslideshow.OpenPersonIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `target` person/pet entity. |
| Set Library View | `com.apple.Photos.FilterLibraryIntent` / `com.apple.mobileslideshow.FilterLibraryIntent` | macOS 27 v78 + iOS 27 Simulator v78 | `viewMode`; cases are `both`, `personal`, and `shared`. Assistant variants `PhotosFilterLibraryAssistantIntent` use the same cases. |
| Change Background Sound | `com.apple.UniversalAccess.UASettingsShortcuts.UASetBackgroundSoundIntent` | macOS 27 v78 | `backgroundSound`, `ShowWhenRun`; confirmed sound cases include `BalancedNoise`, `BrightNoise`, `DarkNoise`, `Ocean`, `Rain`, `Stream`, `Babble`, `Steam`, `Airplane`, `Boat`, `Bus`, `Train`, `RainOnRoof`, `QuietNight`, `Fire`, and `Night`. |
| Set Background Sounds Volume | `com.apple.UniversalAccess.UASettingsShortcuts.UASetBackgroundSoundsVolumeIntent` | macOS 27 v78 | `volumeValue`, `ShowWhenRun`. |
| Set Background Sounds Timer Interval | `com.apple.UniversalAccess.UASettingsShortcuts.UASetBackgroundSoundsTimerIntent` | macOS 27 v78 | `interval`, `duration`, `endInterval`, `always`, `ShowWhenRun`; `interval` cases are `endInterval` and `duration`. |
| Toggle Background Sounds | `com.apple.UniversalAccess.UASettingsShortcuts.UAToggleBackgroundSoundsIntent` | macOS 27 v78 | `operation`, `state`, `ShowWhenRun`; `operation` cases are `turn` and `toggle`. |

The Automators thread reports **Toggle Vehicle Motion Cues**; `AccessibilityUtilities.framework` defines the private `ToggleVehicleMotionCues` / likely `AXToggleVehicleMotionCuesIntent` with `operation` and `state`, while the confirmed ToolKit match is `com.apple.UniversalAccess.UASettingsShortcuts.UAToggleMotionCuesIntent`, localized as **Set Motion Cues** in the local macOS 27 v78 database. The thread also reports **Toggle Hearing Aid Mute**; `AccessibilityUtilities.framework` defines private `ToggleHearingAidMute` / likely `AXToggleHearingAidMuteIntent` with `operation` and `state`, while the iOS 27 ToolKit/runtime metadata localizes `com.apple.HearingApp.MuteVolumeIntent` as **Mute Hearing Device Volume** with no parameters, alongside related Adjust Volume and Select Preset intents. `Set Appearance on Apple TV` uses an Apple TV device picker plus `appearanceToggle`; use the literal values `light` or `dark` for the appearance enum.

The thread also reports **Set Switch Control Switch Set**. This is real in `/System/Library/PrivateFrameworks/AccessibilityUtilities.framework/.../Intents.intentdefinition` as `SetSwitchControlProfile` / likely `AXSetSwitchControlProfileIntent`, with a dynamic `profile` object parameter of type `SwitchControlProfile` and title **Set Switch Control Switch Set**. However, it is not in the local macOS 27 v78 ToolKit database, the hydrated iPhone/iPadOS 27 Simulator v78 ToolKit databases, or ToolRenderer's tool descriptions. The confirmed ToolKit coverage remains **Set Switch Control** as a simple on/off intent plus `switchControlSwitches` as a deep-link target for opening the Switches pane. Do not author Switch Control switch-set changes until an exported shortcut or a device ToolKit database confirms the `WFWorkflowActionIdentifier` and parameter serialization.

## How to Invoke AppIntents

AppIntents use their full identifier in `WFWorkflowActionIdentifier` and include an `AppIntentDescriptor`:
```
<dict>
    <key>WFWorkflowActionIdentifier</key>
    <string>com.apple.shortcuts.OpenShortcutsStaticDeepLinks</string>
    <key>WFWorkflowActionParameters</key>
    <dict>
        <key>AppIntentDescriptor</key>
        <dict>
            <key>BundleIdentifier</key>
            <string>com.apple.shortcuts</string>
            <key>Name</key>
            <string>Open Shortcuts Settings</string>
            <key>TeamIdentifier</key>
            <string>0000000000</string>
            <key>AppIntentIdentifier</key>
            <string>OpenShortcutsStaticDeepLinks</string>
        </dict>
        <!-- Additional parameters as needed -->
    </dict>
</dict>
```

---

## AppIntents by Category

### Settings Deep Links (23 actions)

Open specific Settings panes:

| Identifier | Title |
|------------|-------|
| `com.apple.GameCenter.Settings.DeviceExpertExtension.OpenGameCenterSettingsDeepLinks` | Open Game Center Settings |
| `com.apple.donotdisturb.DoNotDisturbAppIntents.OpenFocusSettingsDynamicDeepLinks` | Open Focus Settings |
| `com.apple.news.NewsSettingsAutomaticDownloadDynamicDeepLinks` | Find News Automatic Download Settings |
| `com.apple.news.NewsSettingsDynamicDeepLinks` | Find News Settings |

### Accessibility (306 actions)

Accessibility settings and controls:

| Identifier Pattern | Description |
|-------------------|-------------|
| `OpenAccessibility*` | Open specific accessibility pane |
| `Ax*` | Accessibility entities and updatable values |
| `UpdateAx*` | Update accessibility setting value |
| `ToggleAx*` | Toggle accessibility feature |

Examples:

### Clock & Alarms (18 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.clock.AddWorldClockIntent` | Add City |
| `com.apple.clock.CancelTimerIntent` | Cancel Timer |
| `com.apple.clock.DeleteAlarmIntent` | Delete Alarms |
| `com.apple.clock.GetCurrentTimerDetailsIntent` | Get Current Timer |
| `com.apple.clock.GetTimeForCityIntent` | Get Time for City |
| `com.apple.clock.LapStopwatchIntent` | Lap Stopwatch |
| `com.apple.clock.OpenAlarmIntent` | Opens Alarm |
| `com.apple.clock.OpenTab` | Open Tab |
| `com.apple.clock.OpenTabIntent` | Open Clock Tab |
| `com.apple.clock.PauseTimerIntent` | Pause Timer |
| `com.apple.clock.RemoveWorldClockIntent` | Remove City |
| `com.apple.clock.ResetStopwatchIntent` | Reset Stopwatch |
| `com.apple.clock.ResumeTimerIntent` | Resume Timer |
| `com.apple.clock.StartStopwatchIntent` | Start Stopwatch |
| `com.apple.clock.StopStopwatchIntent` | Stop the Stopwatch |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent` | Add Alarm |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent` | Find Alarms |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTToggleAlarmIntent` | Toggle Alarm |

### Calendar (26 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.iCal.CreateCalendarIntent` | Create Calendar |
| `com.apple.iCal.CreateEventIntent` | Create Event |
| `com.apple.iCal.CreateEventIntent_v0` | Create Event |
| `com.apple.iCal.DeleteCalendarsIntent` | Delete Calendars |
| `com.apple.iCal.DeleteEventIntent` | Delete Events |
| `com.apple.iCal.DeleteEventIntent_v0` | Delete Events |
| `com.apple.iCal.EditEventIntent` | Edit Event |
| `com.apple.iCal.EditEventIntent_v0` | Edit Event |
| `com.apple.iCal.EmailAttendeesIntent` | Email Attendees |
| `com.apple.iCal.EmailOrganizerIntent` | Email Organizer |
| `com.apple.iCal.EventEntity` | Find Event |
| `com.apple.iCal.FetchTransferableEventByURLIntent` | Fetch Transferable Event By URL Intent |
| `com.apple.iCal.FetchTransferableEventsInRangeIntent` | Fetch Transferable Events In Range Intent <no loc> |
| `com.apple.iCal.HighlightEventIntent` | Highlight Event |
| `com.apple.iCal.InboxItemEntity` | Find Inbox Item |
| `com.apple.iCal.JoinEventIntent` | Join Event |
| `com.apple.iCal.ListEventsIntent` | List Events Intent <no loc> |
| `com.apple.iCal.OpenCalendarEditorIntent` | Open Calendar Editor |
| `com.apple.iCal.OpenCalendarViewIntent` | Open Calendar View |
| `com.apple.iCal.OpenDateIntent` | Open Date |
| `com.apple.iCal.OpenEventDetailsIntent` | Open Event Details |
| `com.apple.iCal.OpenEventEditorIntent` | Open Event Editor |
| `com.apple.iCal.RespondToInboxItemIntent` | Respond to Inbox Item |
| `com.apple.iCal.SetCalendarFocusConfiguration` | Set Calendar Focus Filter |
| `com.apple.iCal.TransferableCalendarEntity` | Find TransferableCalendarEntity <no loc> |
| `com.apple.iCal.TransferableSourceEntity` | Find TransferableSourceEntity <no loc> |

### Reminders (36 actions)

⚠️ **For editing an existing reminder's properties (Due Date, Title, Notes, Priority, Is Completed, Is Flagged, List, Subtasks, URL, Tags, Images, Parent Reminder, When Messaging Person), DO NOT use `com.apple.reminders.UpdateReminderAppIntent`.** Its parameter schema is not published and may change between OS releases. Instead, use the classic WorkflowKit action `is.workflow.actions.setters.reminders` — its schema is fully documented in [PARAMETER_TYPES.md → Reminders — Filter & Setter Schemas](PARAMETER_TYPES.md#reminders--filter--setter-schemas-definitive) and verified against an Apple-built sample.

The AppIntents below exist in the allowlist for completeness (for actions like `CompleteReminderAppIntent` that have no WF equivalent), but **prefer the WF-action path** for any editing workflow.

| Identifier | Title |
|------------|-------|
| `com.apple.reminders.AddOrRemoveTagsAppIntent` | Add or Remove Tags |
| `com.apple.reminders.CompleteReminderAppIntent` | Set Reminder completion state |
| `com.apple.reminders.CompleteRemindersAppIntent` | Set Reminders completion state <no loc> |
| `com.apple.reminders.CreateCustomSmartListAppIntent` | Open New Custom Smart List |
| `com.apple.reminders.CreateGroupAppIntent` | Create Group |
| `com.apple.reminders.CreateSectionAppIntent` | Create Section |
| `com.apple.reminders.DeleteListsAppIntent` | Delete Lists |
| `com.apple.reminders.DeleteRemindersAppIntent` | Delete Reminders and Subtasks |
| `com.apple.reminders.DeleteRemindersListGroupsAppIntent` | Delete Groups |
| `com.apple.reminders.DeleteSectionsAppIntent` | Delete Sections |
| `com.apple.reminders.GroupEntity-UpdatableEntity` | Change Reminders Group Name |
| `com.apple.reminders.ListEntity-UpdatableEntity` | Edit Reminders List |
| `com.apple.reminders.MoveRemindersAppIntent` | Move Reminders |
| `com.apple.reminders.MoveRemindersToListAppIntent` | Move Reminders to a Reminders List <no loc> |
| `com.apple.reminders.MoveRemindersToParentReminderAppIntent` | Move Reminders to become Subtasks of a Parent Reminder <no loc> |
| `com.apple.reminders.MoveRemindersToSectionAppIntent` | Move Reminders to a Reminders List Section <no loc> |
| `com.apple.reminders.OpenGroupAppIntent` | Open Group |
| `com.apple.reminders.OpenReminderAppIntent` | Open Reminder In List |
| `com.apple.reminders.OpenSectionAppIntent` | Reveal Section In List |
| `com.apple.reminders.OpenSmartListAppIntent` | Open Smart List |
| `com.apple.reminders.OpenTagsAppIntent` | Open Tag Browser |
| `com.apple.reminders.RemotePreferencesEntity` | Get User Defaults Entity |
| `com.apple.reminders.SectionEntity-UpdatableEntity` | Edit Reminders List Section |
| `com.apple.reminders.SmartListEntity` | Find Smart List |
| `com.apple.reminders.TTRCreateListAppIntent` | Create List |
| `com.apple.reminders.TTRCreateReminderAppIntent` | Create Reminder |
| `com.apple.reminders.TTROpenListAppIntent` | Open List |
| `com.apple.reminders.TTROpenSmartListAppIntent` | Open List |
| `com.apple.reminders.TTRReminderSetCompletedIntent` | Toggle Reminder completion |
| `com.apple.reminders.TTRSearchRemindersAppIntent` | Search in Reminders |
| `com.apple.reminders.UpdateGroupAppIntent` | Update reminders group properties |
| `com.apple.reminders.UpdateListAppIntent` | Update reminders list properties |
| `com.apple.reminders.UpdateReminderAppIntent` | Update Reminder properties <no loc> |
| `com.apple.reminders.UpdateSectionAppIntent` | Update section properties |
| `com.apple.reminders.UpdateSmartListAppIntent` | Update reminders system smart list properties |
| `com.apple.reminders.UpdateSmartListIsHiddenAppIntent` | Show/Hide Reminders System Smart List |

### Notes (52 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.Notes.AddFileAttachmentLinkAction` | Add File to Note |
| `com.apple.Notes.AddLinkAttachmentLinkAction` | Add Link |
| `com.apple.Notes.AddOrRemoveNoteLockLinkAction` | Add or Remove Note Lock |
| `com.apple.Notes.AddTagsToNotesLinkAction` | Add Tags to Notes |
| `com.apple.Notes.AppendMarkdownToNoteLinkAction` | Append Markdown to Note |
| `com.apple.Notes.ApplyFormattingLinkAction` | Apply Formatting to Selected Text |
| `com.apple.Notes.AttachmentEntity` | Find Attachment |
| `com.apple.Notes.ChangeFolderSettingLinkAction` | Change Folder View Setting |
| `com.apple.Notes.ChangeSettingLinkAction` | Change Notes Setting |
| `com.apple.Notes.ChangeTagSelectionIntent` | Change Tag Selection |
| `com.apple.Notes.CloseAppLocationLinkAction` | Close Notes View |
| `com.apple.Notes.CloseNoteLinkAction` | Close Note |
| `com.apple.Notes.CreateChecklistItemLinkAction` | Append Checklist Item |
| `com.apple.Notes.CreateFolderLinkAction` | Create Folder |
| `com.apple.Notes.CreateNoteFromMarkdownLinkAction` | Create Note from Markdown |
| `com.apple.Notes.CreateTableLinkAction` | Add Table to Note |
| `com.apple.Notes.CreateTagLinkAction` | Create Tag |
| `com.apple.Notes.DeleteAttachmentsLinkAction` | Delete Attachments |
| `com.apple.Notes.DeleteChecklistItemsLinkAction` | Delete Checklist Items |
| `com.apple.Notes.DeleteFoldersLinkAction` | Delete Folders |
| `com.apple.Notes.DeleteNotesLinkAction` | Delete Notes |
| `com.apple.Notes.DeleteTablesLinkAction` | Delete Tables |
| `com.apple.Notes.DeleteTagsLinkAction` | Delete Tags |
| `com.apple.Notes.GetLinkedNotesLinkAction` | Get Linked Notes |
| `com.apple.Notes.InsertAllMentionLinkAction` | Insert All Mention |
| `com.apple.Notes.InsertMentionLinkAction` | Insert Mention |
| `com.apple.Notes.InsertNoteLinkLinkAction` | Insert Note Link |
| `com.apple.Notes.MoveNotesToFolderLinkAction` | Move Notes to Folder |
| `com.apple.Notes.OpenAccountLinkAction` | Open Account |
| `com.apple.Notes.OpenAppLocationLinkAction` | Open Notes View |
| `com.apple.Notes.OpenAttachmentLinkAction` | Open Attachment |
| `com.apple.Notes.OpenChecklistItemLinkAction` | Reveal Checklist Item |
| `com.apple.Notes.OpenFolderLinkAction` | Open Folder |
| `com.apple.Notes.OpenTableLinkAction` | Reveal Table |
| `com.apple.Notes.OpenTagLinkAction` | Open Tag |
| `com.apple.Notes.OpenTopLevelFolderLinkAction` | Open Top-Level Folder |
| `com.apple.Notes.PinNotesLinkAction` | Pin Notes |
| `com.apple.Notes.QuickNoteIntent` | Quick Note |
| `com.apple.Notes.RemoveTagsFromNotesLinkAction` | Remove Tags from Notes |
| `com.apple.Notes.RenameFolderLinkAction` | Rename Folder |
| `com.apple.Notes.ReplaceSelectionLinkAction` | Replace Selected Text |
| `com.apple.Notes.SetAttachmentSizeLinkAction` | Set Attachment Size |
| `com.apple.Notes.SetChecklistItemCheckedLinkActionv2` | Set Checklist Items Checked |
| `com.apple.Notes.SetParagraphStyleLinkAction` | Set Paragraph Style |
| `com.apple.Notes.ShowNotesAppSearchResultsLinkAction` | Show Note and Attachment Search Result |
| `com.apple.Notes.ShowQuickNoteIntent` | Show Quick Note |
| `com.apple.Notes.StartRecordingLinkAction` | Start Audio Recording |
| `com.apple.Notes.TableEntity` | Find Table |
| `com.apple.mobilenotes.SharingExtension` | Create Note |
| `is.workflow.actions.appendnote` | Append to Note |
| `is.workflow.actions.filter.notes` | Find Notes |
| `is.workflow.actions.shownote` | Open Note |

### Safari (31 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.Safari.BookmarkEntity` | Find Bookmarks |
| `com.apple.Safari.BookmarkTabIntent` | Bookmark Tab |
| `com.apple.Safari.BookmarkURLIntent` | Bookmark URL |
| `com.apple.Safari.CloseTab` | Close Tab |
| `com.apple.Safari.CloseTabsAssistantIntent` | Close Tabs |
| `com.apple.Safari.CloseView` | Close View |
| `com.apple.Safari.CloseWindowsIntent` | Close Windows |
| `com.apple.Safari.CreateNewBookmark` | Add Bookmark |
| `com.apple.Safari.CreateNewTab` | Create New Tab |
| `com.apple.Safari.CreateNewTabGroup` | Create Tab Group |
| `com.apple.Safari.CreateNewWindow` | Create Window |
| `com.apple.Safari.CreateTabAssistantIntent` | Create Tab |
| `com.apple.Safari.DeleteBookmarks` | Delete Bookmarks |
| `com.apple.Safari.DeleteTabGroups` | Delete Tab Groups |
| `com.apple.Safari.FindOnPage` | Find on Page |
| `com.apple.Safari.LoadURLInTab` | Open Link |
| `com.apple.Safari.MoveTabsToTabGroup` | Move Tabs to Tab Group |
| `com.apple.Safari.MoveTabsToWindowIntent` | Move Tabs to Window |
| `com.apple.Safari.OpenBookmark` | Open Bookmark |
| `com.apple.Safari.OpenBookmarkAssistantIntent` | Open Bookmark |
| `com.apple.Safari.OpenTab` | Switch Tab |
| `com.apple.Safari.OpenTabGroup` | Open Tab Group |
| `com.apple.Safari.OpenTabGroupForFocus` | Set Safari Focus Filter |
| `com.apple.Safari.OpenView` | Open View |
| `com.apple.Safari.QuickWebsiteSearchIntent` | Search Website |
| `com.apple.Safari.QuickWebsiteSearchProviderEntity` | Find browser_SearchableWebsiteEntity_1.0.0_entity_type_display_representation |
| `com.apple.Safari.SearchTabs` | Search Tabs |
| `com.apple.Safari.ShowWindowIntent` | Show Window |
| `com.apple.Safari.TabEntity` | Find Tabs |
| `com.apple.Safari.TabGroupEntity` | Find Tab Groups |
| `com.apple.Safari.WindowEntity` | Find Window |

### Home (32 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.Home.ActivateSceneIntent` | Activate Scene |
| `com.apple.Home.AutomateAttributeValueIntent` | Automate Set Attribute Value |
| `com.apple.Home.AutomateSceneIntent` | Automate Scene |
| `com.apple.Home.CameraClipEntity` | Find  |
| `com.apple.Home.DeltaAttributeValueIntent` | Delta Attribute |
| `com.apple.Home.DeviceEntity` | Find Device |
| `com.apple.Home.ErrorIntent` | Error Intent |
| `com.apple.Home.ForecastWidgetConfiguration` | Show the Grid Forecast for a Home or your location. |
| `com.apple.Home.GetAttributeValueIntent` | Get Attribute |
| `com.apple.Home.GetDeviceInfoIntent` | Get Device Info |
| `com.apple.Home.HistoricalUsageWidgetConfiguration` | Select Home |
| `com.apple.Home.HomeAppIntentsExtensionTestAppIntent` | HomeAppIntentsExtensionTestAppIntent |
| `com.apple.Home.HomeEntity` | Find Selected Home |
| `com.apple.Home.HomeSingleTileConfigurationIntent` | Scene or Accessory |
| `com.apple.Home.HomeXLModuleConfigurationIntent` | Accessories |
| `com.apple.Home.OpenURLInHomeIntent` | Open Accessory or Scene in Home app |
| `com.apple.Home.RecommendedItemIntent` | Recommended Item |
| `com.apple.Home.RoomEntity` | Find Room |
| `com.apple.Home.SceneEntity` | Find Scene |
| `com.apple.Home.SecureToggleIntent` | Toggle Accessory or Scene |
| `com.apple.Home.SelectedHomeEntity` | Find Selected Home |
| `com.apple.Home.SetAttributeValueIntent` | Set Attribute |
| `com.apple.Home.ShowDeviceResultIntent` | Show Device Result |
| `com.apple.Home.ShowErrorIntent` | Show Error |
| `com.apple.Home.ShowNavigationIntent` | Show Navigation |
| `com.apple.Home.ShowSceneResultIntent` | Show Scene Result |
| `com.apple.Home.TileControlAction` | ToggleIntentTitle |
| `com.apple.Home.ToggleAttributeIntent` | Toggle Attribute |
| `com.apple.Home.ToggleControlConfigurationIntent` | Scene or Accessory |
| `com.apple.Home.ToggleIntent` | Toggle Accessory or Scene |
| `com.apple.Home.UtilityRateInfoWidgetConfiguration` | Select Home |
| `com.apple.Home.ZoneEntity` | Find Zone |

### Photos (69 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.Photos.AddAssetsToAlbumIntent` | Add Photos To Album |
| `com.apple.Photos.ApplyFilterIntent` | Apply Filter |
| `com.apple.Photos.ApplyStyleIntent` | Apply Style |
| `com.apple.Photos.CleanupIntent` | Clean Up |
| `com.apple.Photos.CopyEditsIntent` | Copy Edits |
| `com.apple.Photos.CreateAlbumIntent` | Create Album |
| `com.apple.Photos.CreateAssetsIntent` | Save to Photos |
| `com.apple.Photos.CropIntent` | Crop |
| `com.apple.Photos.DeleteAlbumsIntent` | Delete Albums |
| `com.apple.Photos.DeleteAssetsIntent` | Delete Photos |
| `com.apple.Photos.DuplicateAssetsIntent` | Duplicate Photos |
| `com.apple.Photos.EditAssetIntent` | Edit Photo |
| `com.apple.Photos.EnableDepthIntent` | Portrait Mode |
| `com.apple.Photos.EnhanceIntent` | Auto Enhance |
| `com.apple.Photos.FavoriteAssetsIntent` | Favorite Photos |
| `com.apple.Photos.FavoriteMemoriesIntent` | Favorite Memories |
| `com.apple.Photos.FavoritePeopleIntent` | Favorite People or Pets |
| `com.apple.Photos.FilterLibraryIntent` | Set Library View |
| `com.apple.Photos.HideAssetsIntent` | Hide Photos |
| `com.apple.Photos.HidePeopleIntent` | Hide People or Pets |
| `com.apple.Photos.MarkupIntent` | Markup |
| `com.apple.Photos.MoveAssetsToPersonalLibraryIntent` | Move to Personal Library |
| `com.apple.Photos.MoveAssetsToSharedLibraryIntent` | Move to Shared Library |
| `com.apple.Photos.OpenAlbumIntent` | Open Album |
| `com.apple.Photos.OpenAssetIntent` | Open Photo |
| `com.apple.Photos.OpenDestinationIntent` | Open View |
| `com.apple.Photos.OpenMemoryCreationViewIntent` | Create Memory |
| `com.apple.Photos.OpenMemoryIntent` | Open Memory |
| `com.apple.Photos.OpenPersonIntent` | Open Person |
| `com.apple.Photos.PLPhotosReliveWidgetConfigurationIntent` | Photos Relive Widget Configuration |
| `com.apple.Photos.PasteEditsIntent` | Paste Edits |
| `com.apple.Photos.PhotosAddAssetsToAlbumAssistantIntent` | Add Photos to Album |
| `com.apple.Photos.PhotosCleanupPhotoAssistantIntent` | Cleanup |
| `com.apple.Photos.PhotosCopyEditsAssistantIntent` | Copy Edits |
| `com.apple.Photos.PhotosCreateAlbumAssistantIntent` | Create Album |
| `com.apple.Photos.PhotosCreateAssetsAssistantIntent` | Create Photos |
| `com.apple.Photos.PhotosCropAssistantIntent` | Crop Photo |
| `com.apple.Photos.PhotosDeleteAlbumsAssistantIntent` | Delete Albums |
| `com.apple.Photos.PhotosDeleteAssetsAssistantIntent` | Delete Photos |
| `com.apple.Photos.PhotosDuplicateAssetsAssistantIntent` | Duplicate Photos |
| `com.apple.Photos.PhotosPasteEditsAssistantIntent` | Paste Edits |
| `com.apple.Photos.PhotosReliveWidgetFeaturedConfiguration` | Photos Relive Featured Widget Configuration |
| `com.apple.Photos.PhotosRemoveAssetsFromAlbumAssistantIntent` | Remove Photos from Album |
| `com.apple.Photos.PhotosSearchAssistantIntent` | Search Photos |
| `com.apple.Photos.PhotosSetDepthAssistantIntent` | Set Depth |
| `com.apple.Photos.PhotosSetExposureAssistantIntent` | Set Exposure |
| `com.apple.Photos.PhotosSetFilterAssistantIntent` | Apply Filter |
| `com.apple.Photos.PhotosSetRotationAssistantIntent` | Rotate Photo |
| `com.apple.Photos.PhotosSetSaturationAssistantIntent` | Set Saturation |
| `com.apple.Photos.PhotosSetWarmthAssistantIntent` | Set Warmth |
| `com.apple.Photos.PhotosStraightenAssistantIntent` | Straighten Photo |
| `com.apple.Photos.PhotosToggleDepthAssistantIntent` | Toggle Depth |
| `com.apple.Photos.PhotosToggleSuggestedEditsAssistantIntent` | Enhance Photo |
| `com.apple.Photos.PhotosUpdateAlbumAssistantIntent` | Rename Album |
| `com.apple.Photos.PhotosUpdateAssetAssistantIntent` | Update Photo |
| `com.apple.Photos.PhotosUpdateRecognizedPersonAssistantIntent` | Update Person |
| `com.apple.Photos.RemoveAssetsFromAlbumIntent` | Remove Photos From Album |
| `com.apple.Photos.RenameAlbumIntent` | Rename Album |
| `com.apple.Photos.RenamePersonIntent` | Rename Person |
| `com.apple.Photos.RevealAlbumsIntent` | REVEAL_ALBUMS_INTENT_TITLE |
| `com.apple.Photos.RevealAssetsIntent` | REVEAL_ASSETS_INTENT_TITLE |
| `com.apple.Photos.RotateIntent` | Rotate |
| `com.apple.Photos.SetApertureIntent` | Set Aperture |
| `com.apple.Photos.SetAudioMixIntent` | Set Audio Mix |
| `com.apple.Photos.SetExposureIntent` | Set Exposure |
| `com.apple.Photos.SetPlaybackRateIntent` | Set Playback Speed |
| `com.apple.Photos.SetSaturationIntent` | Set Saturation |
| `com.apple.Photos.SetWarmthIntent` | Set Warmth |
| `com.apple.Photos.StraightenIntent` | Straighten |

### Music (1 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.ShortcutsActions.PlayMusicTopHitAction` | Play Music |

### Writing Tools (3 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.AppKit.WritingToolsComposeIntent` | Text Compose |
| `com.apple.AppKit.WritingToolsProofreadIntent` | Proofread |
| `com.apple.AppKit.WritingToolsRewriteIntent` | Rewrite |

#### Apple Intelligence / AppKit Runtime Actions

macOS 27 ToolKit v78 exposes additional AppKit and Writing Tools intents that operate on a target app/process/window context. They are packaged in the v78 parameter catalog and validator can check top-level keys, simple enum values, and booleans, but authoring useful shortcuts still requires real app/window context values such as `app`, `processInstanceIdentifier`, `targetWindowIdentifier`, and `targetFrame`.

| Identifier | Display Name | Observed Parameters |
|------------|--------------|---------------------|
| `com.apple.AppKit.FetchIntelligenceCommands` | Fetch Intelligence Commands | `app`, `processInstanceIdentifier`, `cachedIfAvailable`, `includeUntitled`, `includeNonPerformable` |
| `com.apple.AppKit.InsertIntelligenceText` | Insert Intelligence Text | `app`, `processInstanceIdentifier`, `text`, `replaceExisting`, `targetWindowIdentifier`, `targetFrame` |
| `com.apple.AppKit.PresentWritingToolsResult` | Present Writing Tools Result | `app`, `text`, `replaceExisting`, `targetWindowIdentifier` |
| `com.apple.AppKit.RequestEditingContext` | Request Editing Context | `app`, `targetWindowIdentifier`, `targetFrame` |
| `com.apple.AppKit.RunIntelligenceCommand` | Run Intelligence Command | `app`, `processInstanceIdentifier`, `command` |
| `com.apple.AppKit.RunIntelligenceCommandForKey` | Run Intelligence Command For Key | `app`, `processInstanceIdentifier`, `identifier`, `command`, `hierarchyComponents` |
| `com.apple.AppKit.WritingToolsCanPerformIntent` | Can Perform Writing Tools | `app`, `processInstanceIdentifier` |
| `com.apple.AppKit.WritingToolsOpenEndedIntent` | Open Ended | `app`, `processInstanceIdentifier`, `prompt` |
| `com.apple.AppKit.WritingToolsPartnerIntent` | Text Compose | `app`, `processInstanceIdentifier`, `prompt`, `externalProviderID` |
| `com.apple.AppKit.WritingToolsSummarizeIntent` | Summarize | `app`, `processInstanceIdentifier` |
| `com.apple.AppKit.WritingToolsTransformKeyPointsIntent` | Key Points | `app`, `processInstanceIdentifier` |
| `com.apple.AppKit.WritingToolsTransformListIntent` | List | `app`, `processInstanceIdentifier` |
| `com.apple.AppKit.WritingToolsTransformTableIntent` | Table | `app`, `processInstanceIdentifier` |

### Voice Memos (24 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.VoiceMemos.AudioQualityEntity` | Get Audio Quality |
| `com.apple.VoiceMemos.AudioQualityEntity-UpdatableEntity` | Edit Audio Quality |
| `com.apple.VoiceMemos.ChangeRecordingPlaybackSetting` | Change Recording Playback Setting |
| `com.apple.VoiceMemos.ClearDeletedEntity` | Get Clear Deleted |
| `com.apple.VoiceMemos.ClearDeletedEntity-UpdatableEntity` | Edit Clear Deleted |
| `com.apple.VoiceMemos.CreateFolder` | Create Folder |
| `com.apple.VoiceMemos.DeleteFolder` | Delete Folders |
| `com.apple.VoiceMemos.DeleteRecording` | Delete Recordings |
| `com.apple.VoiceMemos.LocationBasedNamingEntity` | Get Location-based Naming |
| `com.apple.VoiceMemos.LocationBasedNamingEntity-UpdatableEntity` | Edit Location-based Naming |
| `com.apple.VoiceMemos.OpenFolder` | Open Folder |
| `com.apple.VoiceMemos.OpenResetAnalyticsIdentifierEntity` | Open Reset Identifier |
| `com.apple.VoiceMemos.PlaybackVoiceMemoIntent` | Play Recording |
| `com.apple.VoiceMemos.RCCombineRecordings` | Combine Recordings |
| `com.apple.VoiceMemos.RCControlCenterToggleRecording` | CONTROL_CENTER_TOGGLE_RECORDING_INTENT_TITLE |
| `com.apple.VoiceMemos.RCImportRecording` | Import Recording |
| `com.apple.VoiceMemos.RCRecordingEntity` | Find Recordings |
| `com.apple.VoiceMemos.RecordVoiceMemoIntent` | Create Recording |
| `com.apple.VoiceMemos.ResetAnalyticsIdentifierEntity` | Get Reset Identifier |
| `com.apple.VoiceMemos.SearchRecordings` | Search in Voice Memos |
| `com.apple.VoiceMemos.SelectRecording` | Select Recording |
| `com.apple.VoiceMemos.StopRecording` | Stop Recording |
| `com.apple.VoiceMemos.ToggleRecording` | Voice Memo |
| `com.apple.VoiceMemos.WFAppSettingEntityUpdaterAction` | Change Voice Memos Settings |

### Shortcuts (23 actions)

| Identifier | Title |
|------------|-------|
| `com.apple.VoiceMemos.WFGetAppSettingAction` | Get Voice Memos Settings |
| `com.apple.news.WFGetAppSettingAction` | Get News Settings |
| `com.apple.shortcuts.AddShortcutToHomeScreenAction` | Add Shortcut to Home Screen |
| `com.apple.shortcuts.ChangeShortcutIconAction` | Change Shortcut Icon |
| `com.apple.shortcuts.CreateFolderAction` | Create Folder |
| `com.apple.shortcuts.CreateShortcutiCloudLinkAction` | Create iCloud Link for Shortcut |
| `com.apple.shortcuts.CreateWorkflowAction` | Create Shortcut |
| `com.apple.shortcuts.DeleteWorkflowAction` | Delete Shortcuts |
| `com.apple.shortcuts.GetShortcutAttributesAction` | Get Shortcut Attributes |
| `com.apple.shortcuts.MoveShortcutToFolderAction` | Move Shortcut |
| `com.apple.shortcuts.OpenAppIntent` | Open App |
| `com.apple.shortcuts.OpenNavigationDestinationAction` | Open Folder |
| `com.apple.shortcuts.OpenShortcutsStaticDeepLinks` | Open Shortcuts Settings *(iOS-only — see Platform Availability)* |
| `com.apple.shortcuts.OpenWorkflowAction` | Open Shortcut |
| `com.apple.shortcuts.RenameShortcutAction` | Rename Shortcut |
| `com.apple.shortcuts.RunShortcutConfigurationIntent` | Shortcut |
| `com.apple.shortcuts.RunShortcutFromCollectionIntent` | Run Shortcut from Folder |
| `com.apple.shortcuts.RunShortcutIntent` | Run Shortcut |
| `com.apple.shortcuts.SearchActionDrawerAction` | Search Shortcuts Actions |
| `com.apple.shortcuts.SearchShortcutsAction` | Search in Shortcuts |
| `com.apple.shortcuts.SetShortcutAttributesAction` | Set Shortcut Attributes |
| `com.apple.shortcuts.ShortcutsFolderConfigurationIntent` | Shortcuts Folder |
| `com.apple.shortcuts.StopWorkflowAction` | Stop Shortcut |

### System Controls (52 actions)

Toggle and set system settings:

| Pattern | Description |
|---------|-------------|
| `Set*` | Set system setting |
| `Toggle*` | Toggle system setting |
| `Update*` | Update system setting value |

Examples:
- `com.apple.Home.SetAttributeValueIntent` - Set Attribute
- `com.apple.Home.ToggleAttributeIntent` - Toggle Attribute
- `com.apple.AddressBook.UpdateContactIntent` - Update Contact Details

### Data & Search (37 actions)

| Pattern | Description |
|---------|-------------|
| `Find*` | Find/search items |
| `Get*` | Get data |
| `Search*` | Search for content |

Examples:
- `com.apple.Safari.FindOnPage` - Find on Page
- `com.apple.Home.GetAttributeValueIntent` - Get Attribute
- `com.apple.AddressBook.SearchInContactsIntent` - Search in Contacts App

------------|-------|
| `com.apple.GameCenter.Settings.DeviceExpertExtension.OpenGameCenterSettingsDeepLinks` | Open Game Center Settings |
| `com.apple.donotdisturb.DoNotDisturbAppIntents.OpenFocusSettingsDynamicDeepLinks` | Open Focus Settings |
| `com.apple.news.NewsSettingsAutomaticDownloadDynamicDeepLinks` | Find News Automatic Download Settings |
| `com.apple.news.NewsSettingsDynamicDeepLinks` | Find News Settings |

### Accessibility (306 actions)

Accessibility settings and controls:

| Identifier Pattern | Description |
|-------------------|-------------|
| `OpenAccessibility*` | Open specific accessibility pane |
| `Ax*` | Accessibility entities and updatable values |
| `UpdateAx*` | Update accessibility setting value |
| `ToggleAx*` | Toggle accessibility feature |

Examples:

### Clock & Alarms (18 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.clock.AddWorldClockIntent` | Add City |
| `com.apple.clock.CancelTimerIntent` | Cancel Timer |
| `com.apple.clock.DeleteAlarmIntent` | Delete Alarms |
| `com.apple.clock.GetCurrentTimerDetailsIntent` | Get Current Timer |
| `com.apple.clock.GetTimeForCityIntent` | Get Time for City |
| `com.apple.clock.LapStopwatchIntent` | Lap Stopwatch |
| `com.apple.clock.OpenAlarmIntent` | Opens Alarm |
| `com.apple.clock.OpenTab` | Open Tab |
| `com.apple.clock.OpenTabIntent` | Open Clock Tab |
| `com.apple.clock.PauseTimerIntent` | Pause Timer |
| `com.apple.clock.RemoveWorldClockIntent` | Remove City |
| `com.apple.clock.ResetStopwatchIntent` | Reset Stopwatch |
| `com.apple.clock.ResumeTimerIntent` | Resume Timer |
| `com.apple.clock.StartStopwatchIntent` | Start Stopwatch |
| `com.apple.clock.StopStopwatchIntent` | Stop the Stopwatch |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent` | Add Alarm |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent` | Find Alarms |
| `com.apple.mobiletimer-framework.MobileTimerIntents.MTToggleAlarmIntent` | Toggle Alarm |

### Calendar (26 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.iCal.CreateCalendarIntent` | Create Calendar |
| `com.apple.iCal.CreateEventIntent` | Create Event |
| `com.apple.iCal.CreateEventIntent_v0` | Create Event |
| `com.apple.iCal.DeleteCalendarsIntent` | Delete Calendars |
| `com.apple.iCal.DeleteEventIntent` | Delete Events |
| `com.apple.iCal.DeleteEventIntent_v0` | Delete Events |
| `com.apple.iCal.EditEventIntent` | Edit Event |
| `com.apple.iCal.EditEventIntent_v0` | Edit Event |
| `com.apple.iCal.EmailAttendeesIntent` | Email Attendees |
| `com.apple.iCal.EmailOrganizerIntent` | Email Organizer |
| `com.apple.iCal.EventEntity` | Find Event |
| `com.apple.iCal.FetchTransferableEventByURLIntent` | Fetch Transferable Event By URL Intent |
| `com.apple.iCal.FetchTransferableEventsInRangeIntent` | Fetch Transferable Events In Range Intent <no loc> |
| `com.apple.iCal.HighlightEventIntent` | Highlight Event |
| `com.apple.iCal.InboxItemEntity` | Find Inbox Item |
| `com.apple.iCal.JoinEventIntent` | Join Event |
| `com.apple.iCal.ListEventsIntent` | List Events Intent <no loc> |
| `com.apple.iCal.OpenCalendarEditorIntent` | Open Calendar Editor |
| `com.apple.iCal.OpenCalendarViewIntent` | Open Calendar View |
| `com.apple.iCal.OpenDateIntent` | Open Date |
| `com.apple.iCal.OpenEventDetailsIntent` | Open Event Details |
| `com.apple.iCal.OpenEventEditorIntent` | Open Event Editor |
| `com.apple.iCal.RespondToInboxItemIntent` | Respond to Inbox Item |
| `com.apple.iCal.SetCalendarFocusConfiguration` | Set Calendar Focus Filter |
| `com.apple.iCal.TransferableCalendarEntity` | Find TransferableCalendarEntity <no loc> |
| `com.apple.iCal.TransferableSourceEntity` | Find TransferableSourceEntity <no loc> |

### Reminders (36 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.reminders.AddOrRemoveTagsAppIntent` | Add or Remove Tags |
| `com.apple.reminders.CompleteReminderAppIntent` | Set Reminder completion state |
| `com.apple.reminders.CompleteRemindersAppIntent` | Set Reminders completion state <no loc> |
| `com.apple.reminders.CreateCustomSmartListAppIntent` | Open New Custom Smart List |
| `com.apple.reminders.CreateGroupAppIntent` | Create Group |
| `com.apple.reminders.CreateSectionAppIntent` | Create Section |
| `com.apple.reminders.DeleteListsAppIntent` | Delete Lists |
| `com.apple.reminders.DeleteRemindersAppIntent` | Delete Reminders and Subtasks |
| `com.apple.reminders.DeleteRemindersListGroupsAppIntent` | Delete Groups |
| `com.apple.reminders.DeleteSectionsAppIntent` | Delete Sections |
| `com.apple.reminders.GroupEntity-UpdatableEntity` | Change Reminders Group Name |
| `com.apple.reminders.ListEntity-UpdatableEntity` | Edit Reminders List |
| `com.apple.reminders.MoveRemindersAppIntent` | Move Reminders |
| `com.apple.reminders.MoveRemindersToListAppIntent` | Move Reminders to a Reminders List <no loc> |
| `com.apple.reminders.MoveRemindersToParentReminderAppIntent` | Move Reminders to become Subtasks of a Parent Reminder <no loc> |
| `com.apple.reminders.MoveRemindersToSectionAppIntent` | Move Reminders to a Reminders List Section <no loc> |
| `com.apple.reminders.OpenGroupAppIntent` | Open Group |
| `com.apple.reminders.OpenReminderAppIntent` | Open Reminder In List |
| `com.apple.reminders.OpenSectionAppIntent` | Reveal Section In List |
| `com.apple.reminders.OpenSmartListAppIntent` | Open Smart List |
| `com.apple.reminders.OpenTagsAppIntent` | Open Tag Browser |
| `com.apple.reminders.RemotePreferencesEntity` | Get User Defaults Entity |
| `com.apple.reminders.SectionEntity-UpdatableEntity` | Edit Reminders List Section |
| `com.apple.reminders.SmartListEntity` | Find Smart List |
| `com.apple.reminders.TTRCreateListAppIntent` | Create List |
| `com.apple.reminders.TTRCreateReminderAppIntent` | Create Reminder |
| `com.apple.reminders.TTROpenListAppIntent` | Open List |
| `com.apple.reminders.TTROpenSmartListAppIntent` | Open List |
| `com.apple.reminders.TTRReminderSetCompletedIntent` | Toggle Reminder completion |
| `com.apple.reminders.TTRSearchRemindersAppIntent` | Search in Reminders |
| `com.apple.reminders.UpdateGroupAppIntent` | Update reminders group properties |
| `com.apple.reminders.UpdateListAppIntent` | Update reminders list properties |
| `com.apple.reminders.UpdateReminderAppIntent` | Update Reminder properties <no loc> |
| `com.apple.reminders.UpdateSectionAppIntent` | Update section properties |
| `com.apple.reminders.UpdateSmartListAppIntent` | Update reminders system smart list properties |
| `com.apple.reminders.UpdateSmartListIsHiddenAppIntent` | Show/Hide Reminders System Smart List |

### Notes (52 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.Notes.AddFileAttachmentLinkAction` | Add File to Note |
| `com.apple.Notes.AddLinkAttachmentLinkAction` | Add Link |
| `com.apple.Notes.AddOrRemoveNoteLockLinkAction` | Add or Remove Note Lock |
| `com.apple.Notes.AddTagsToNotesLinkAction` | Add Tags to Notes |
| `com.apple.Notes.AppendMarkdownToNoteLinkAction` | Append Markdown to Note |
| `com.apple.Notes.ApplyFormattingLinkAction` | Apply Formatting to Selected Text |
| `com.apple.Notes.AttachmentEntity` | Find Attachment |
| `com.apple.Notes.ChangeFolderSettingLinkAction` | Change Folder View Setting |
| `com.apple.Notes.ChangeSettingLinkAction` | Change Notes Setting |
| `com.apple.Notes.ChangeTagSelectionIntent` | Change Tag Selection |
| `com.apple.Notes.CloseAppLocationLinkAction` | Close Notes View |
| `com.apple.Notes.CloseNoteLinkAction` | Close Note |
| `com.apple.Notes.CreateChecklistItemLinkAction` | Append Checklist Item |
| `com.apple.Notes.CreateFolderLinkAction` | Create Folder |
| `com.apple.Notes.CreateNoteFromMarkdownLinkAction` | Create Note from Markdown |
| `com.apple.Notes.CreateTableLinkAction` | Add Table to Note |
| `com.apple.Notes.CreateTagLinkAction` | Create Tag |
| `com.apple.Notes.DeleteAttachmentsLinkAction` | Delete Attachments |
| `com.apple.Notes.DeleteChecklistItemsLinkAction` | Delete Checklist Items |
| `com.apple.Notes.DeleteFoldersLinkAction` | Delete Folders |
| `com.apple.Notes.DeleteNotesLinkAction` | Delete Notes |
| `com.apple.Notes.DeleteTablesLinkAction` | Delete Tables |
| `com.apple.Notes.DeleteTagsLinkAction` | Delete Tags |
| `com.apple.Notes.GetLinkedNotesLinkAction` | Get Linked Notes |
| `com.apple.Notes.InsertAllMentionLinkAction` | Insert All Mention |
| `com.apple.Notes.InsertMentionLinkAction` | Insert Mention |
| `com.apple.Notes.InsertNoteLinkLinkAction` | Insert Note Link |
| `com.apple.Notes.MoveNotesToFolderLinkAction` | Move Notes to Folder |
| `com.apple.Notes.OpenAccountLinkAction` | Open Account |
| `com.apple.Notes.OpenAppLocationLinkAction` | Open Notes View |
| `com.apple.Notes.OpenAttachmentLinkAction` | Open Attachment |
| `com.apple.Notes.OpenChecklistItemLinkAction` | Reveal Checklist Item |
| `com.apple.Notes.OpenFolderLinkAction` | Open Folder |
| `com.apple.Notes.OpenTableLinkAction` | Reveal Table |
| `com.apple.Notes.OpenTagLinkAction` | Open Tag |
| `com.apple.Notes.OpenTopLevelFolderLinkAction` | Open Top-Level Folder |
| `com.apple.Notes.PinNotesLinkAction` | Pin Notes |
| `com.apple.Notes.QuickNoteIntent` | Quick Note |
| `com.apple.Notes.RemoveTagsFromNotesLinkAction` | Remove Tags from Notes |
| `com.apple.Notes.RenameFolderLinkAction` | Rename Folder |
| `com.apple.Notes.ReplaceSelectionLinkAction` | Replace Selected Text |
| `com.apple.Notes.SetAttachmentSizeLinkAction` | Set Attachment Size |
| `com.apple.Notes.SetChecklistItemCheckedLinkActionv2` | Set Checklist Items Checked |
| `com.apple.Notes.SetParagraphStyleLinkAction` | Set Paragraph Style |
| `com.apple.Notes.ShowNotesAppSearchResultsLinkAction` | Show Note and Attachment Search Result |
| `com.apple.Notes.ShowQuickNoteIntent` | Show Quick Note |
| `com.apple.Notes.StartRecordingLinkAction` | Start Audio Recording |
| `com.apple.Notes.TableEntity` | Find Table |
| `com.apple.mobilenotes.SharingExtension` | Create Note |
| `is.workflow.actions.appendnote` | Append to Note |
| `is.workflow.actions.filter.notes` | Find Notes |
| `is.workflow.actions.shownote` | Open Note |

### Safari (31 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.Safari.BookmarkEntity` | Find Bookmarks |
| `com.apple.Safari.BookmarkTabIntent` | Bookmark Tab |
| `com.apple.Safari.BookmarkURLIntent` | Bookmark URL |
| `com.apple.Safari.CloseTab` | Close Tab |
| `com.apple.Safari.CloseTabsAssistantIntent` | Close Tabs |
| `com.apple.Safari.CloseView` | Close View |
| `com.apple.Safari.CloseWindowsIntent` | Close Windows |
| `com.apple.Safari.CreateNewBookmark` | Add Bookmark |
| `com.apple.Safari.CreateNewTab` | Create New Tab |
| `com.apple.Safari.CreateNewTabGroup` | Create Tab Group |
| `com.apple.Safari.CreateNewWindow` | Create Window |
| `com.apple.Safari.CreateTabAssistantIntent` | Create Tab |
| `com.apple.Safari.DeleteBookmarks` | Delete Bookmarks |
| `com.apple.Safari.DeleteTabGroups` | Delete Tab Groups |
| `com.apple.Safari.FindOnPage` | Find on Page |
| `com.apple.Safari.LoadURLInTab` | Open Link |
| `com.apple.Safari.MoveTabsToTabGroup` | Move Tabs to Tab Group |
| `com.apple.Safari.MoveTabsToWindowIntent` | Move Tabs to Window |
| `com.apple.Safari.OpenBookmark` | Open Bookmark |
| `com.apple.Safari.OpenBookmarkAssistantIntent` | Open Bookmark |
| `com.apple.Safari.OpenTab` | Switch Tab |
| `com.apple.Safari.OpenTabGroup` | Open Tab Group |
| `com.apple.Safari.OpenTabGroupForFocus` | Set Safari Focus Filter |
| `com.apple.Safari.OpenView` | Open View |
| `com.apple.Safari.QuickWebsiteSearchIntent` | Search Website |
| `com.apple.Safari.QuickWebsiteSearchProviderEntity` | Find browser_SearchableWebsiteEntity_1.0.0_entity_type_display_representation |
| `com.apple.Safari.SearchTabs` | Search Tabs |
| `com.apple.Safari.ShowWindowIntent` | Show Window |
| `com.apple.Safari.TabEntity` | Find Tabs |
| `com.apple.Safari.TabGroupEntity` | Find Tab Groups |
| `com.apple.Safari.WindowEntity` | Find Window |

### Home (32 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.Home.ActivateSceneIntent` | Activate Scene |
| `com.apple.Home.AutomateAttributeValueIntent` | Automate Set Attribute Value |
| `com.apple.Home.AutomateSceneIntent` | Automate Scene |
| `com.apple.Home.CameraClipEntity` | Find  |
| `com.apple.Home.DeltaAttributeValueIntent` | Delta Attribute |
| `com.apple.Home.DeviceEntity` | Find Device |
| `com.apple.Home.ErrorIntent` | Error Intent |
| `com.apple.Home.ForecastWidgetConfiguration` | Show the Grid Forecast for a Home or your location. |
| `com.apple.Home.GetAttributeValueIntent` | Get Attribute |
| `com.apple.Home.GetDeviceInfoIntent` | Get Device Info |
| `com.apple.Home.HistoricalUsageWidgetConfiguration` | Select Home |
| `com.apple.Home.HomeAppIntentsExtensionTestAppIntent` | HomeAppIntentsExtensionTestAppIntent |
| `com.apple.Home.HomeEntity` | Find Selected Home |
| `com.apple.Home.HomeSingleTileConfigurationIntent` | Scene or Accessory |
| `com.apple.Home.HomeXLModuleConfigurationIntent` | Accessories |
| `com.apple.Home.OpenURLInHomeIntent` | Open Accessory or Scene in Home app |
| `com.apple.Home.RecommendedItemIntent` | Recommended Item |
| `com.apple.Home.RoomEntity` | Find Room |
| `com.apple.Home.SceneEntity` | Find Scene |
| `com.apple.Home.SecureToggleIntent` | Toggle Accessory or Scene |
| `com.apple.Home.SelectedHomeEntity` | Find Selected Home |
| `com.apple.Home.SetAttributeValueIntent` | Set Attribute |
| `com.apple.Home.ShowDeviceResultIntent` | Show Device Result |
| `com.apple.Home.ShowErrorIntent` | Show Error |
| `com.apple.Home.ShowNavigationIntent` | Show Navigation |
| `com.apple.Home.ShowSceneResultIntent` | Show Scene Result |
| `com.apple.Home.TileControlAction` | ToggleIntentTitle |
| `com.apple.Home.ToggleAttributeIntent` | Toggle Attribute |
| `com.apple.Home.ToggleControlConfigurationIntent` | Scene or Accessory |
| `com.apple.Home.ToggleIntent` | Toggle Accessory or Scene |
| `com.apple.Home.UtilityRateInfoWidgetConfiguration` | Select Home |
| `com.apple.Home.ZoneEntity` | Find Zone |

### Photos (69 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.Photos.AddAssetsToAlbumIntent` | Add Photos To Album |
| `com.apple.Photos.ApplyFilterIntent` | Apply Filter |
| `com.apple.Photos.ApplyStyleIntent` | Apply Style |
| `com.apple.Photos.CleanupIntent` | Clean Up |
| `com.apple.Photos.CopyEditsIntent` | Copy Edits |
| `com.apple.Photos.CreateAlbumIntent` | Create Album |
| `com.apple.Photos.CreateAssetsIntent` | Save to Photos |
| `com.apple.Photos.CropIntent` | Crop |
| `com.apple.Photos.DeleteAlbumsIntent` | Delete Albums |
| `com.apple.Photos.DeleteAssetsIntent` | Delete Photos |
| `com.apple.Photos.DuplicateAssetsIntent` | Duplicate Photos |
| `com.apple.Photos.EditAssetIntent` | Edit Photo |
| `com.apple.Photos.EnableDepthIntent` | Portrait Mode |
| `com.apple.Photos.EnhanceIntent` | Auto Enhance |
| `com.apple.Photos.FavoriteAssetsIntent` | Favorite Photos |
| `com.apple.Photos.FavoriteMemoriesIntent` | Favorite Memories |
| `com.apple.Photos.FavoritePeopleIntent` | Favorite People or Pets |
| `com.apple.Photos.FilterLibraryIntent` | Set Library View |
| `com.apple.Photos.HideAssetsIntent` | Hide Photos |
| `com.apple.Photos.HidePeopleIntent` | Hide People or Pets |
| `com.apple.Photos.MarkupIntent` | Markup |
| `com.apple.Photos.MoveAssetsToPersonalLibraryIntent` | Move to Personal Library |
| `com.apple.Photos.MoveAssetsToSharedLibraryIntent` | Move to Shared Library |
| `com.apple.Photos.OpenAlbumIntent` | Open Album |
| `com.apple.Photos.OpenAssetIntent` | Open Photo |
| `com.apple.Photos.OpenDestinationIntent` | Open View |
| `com.apple.Photos.OpenMemoryCreationViewIntent` | Create Memory |
| `com.apple.Photos.OpenMemoryIntent` | Open Memory |
| `com.apple.Photos.OpenPersonIntent` | Open Person |
| `com.apple.Photos.PLPhotosReliveWidgetConfigurationIntent` | Photos Relive Widget Configuration |
| `com.apple.Photos.PasteEditsIntent` | Paste Edits |
| `com.apple.Photos.PhotosAddAssetsToAlbumAssistantIntent` | Add Photos to Album |
| `com.apple.Photos.PhotosCleanupPhotoAssistantIntent` | Cleanup |
| `com.apple.Photos.PhotosCopyEditsAssistantIntent` | Copy Edits |
| `com.apple.Photos.PhotosCreateAlbumAssistantIntent` | Create Album |
| `com.apple.Photos.PhotosCreateAssetsAssistantIntent` | Create Photos |
| `com.apple.Photos.PhotosCropAssistantIntent` | Crop Photo |
| `com.apple.Photos.PhotosDeleteAlbumsAssistantIntent` | Delete Albums |
| `com.apple.Photos.PhotosDeleteAssetsAssistantIntent` | Delete Photos |
| `com.apple.Photos.PhotosDuplicateAssetsAssistantIntent` | Duplicate Photos |
| `com.apple.Photos.PhotosPasteEditsAssistantIntent` | Paste Edits |
| `com.apple.Photos.PhotosReliveWidgetFeaturedConfiguration` | Photos Relive Featured Widget Configuration |
| `com.apple.Photos.PhotosRemoveAssetsFromAlbumAssistantIntent` | Remove Photos from Album |
| `com.apple.Photos.PhotosSearchAssistantIntent` | Search Photos |
| `com.apple.Photos.PhotosSetDepthAssistantIntent` | Set Depth |
| `com.apple.Photos.PhotosSetExposureAssistantIntent` | Set Exposure |
| `com.apple.Photos.PhotosSetFilterAssistantIntent` | Apply Filter |
| `com.apple.Photos.PhotosSetRotationAssistantIntent` | Rotate Photo |
| `com.apple.Photos.PhotosSetSaturationAssistantIntent` | Set Saturation |
| `com.apple.Photos.PhotosSetWarmthAssistantIntent` | Set Warmth |
| `com.apple.Photos.PhotosStraightenAssistantIntent` | Straighten Photo |
| `com.apple.Photos.PhotosToggleDepthAssistantIntent` | Toggle Depth |
| `com.apple.Photos.PhotosToggleSuggestedEditsAssistantIntent` | Enhance Photo |
| `com.apple.Photos.PhotosUpdateAlbumAssistantIntent` | Rename Album |
| `com.apple.Photos.PhotosUpdateAssetAssistantIntent` | Update Photo |
| `com.apple.Photos.PhotosUpdateRecognizedPersonAssistantIntent` | Update Person |
| `com.apple.Photos.RemoveAssetsFromAlbumIntent` | Remove Photos From Album |
| `com.apple.Photos.RenameAlbumIntent` | Rename Album |
| `com.apple.Photos.RenamePersonIntent` | Rename Person |
| `com.apple.Photos.RevealAlbumsIntent` | REVEAL_ALBUMS_INTENT_TITLE |
| `com.apple.Photos.RevealAssetsIntent` | REVEAL_ASSETS_INTENT_TITLE |
| `com.apple.Photos.RotateIntent` | Rotate |
| `com.apple.Photos.SetApertureIntent` | Set Aperture |
| `com.apple.Photos.SetAudioMixIntent` | Set Audio Mix |
| `com.apple.Photos.SetExposureIntent` | Set Exposure |
| `com.apple.Photos.SetPlaybackRateIntent` | Set Playback Speed |
| `com.apple.Photos.SetSaturationIntent` | Set Saturation |
| `com.apple.Photos.SetWarmthIntent` | Set Warmth |
| `com.apple.Photos.StraightenIntent` | Straighten |

### Music (1 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.ShortcutsActions.PlayMusicTopHitAction` | Play Music |

### Writing Tools (3 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.AppKit.WritingToolsComposeIntent` | Text Compose |
| `com.apple.AppKit.WritingToolsProofreadIntent` | Proofread |
| `com.apple.AppKit.WritingToolsRewriteIntent` | Rewrite |

### Voice Memos (24 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.VoiceMemos.AudioQualityEntity` | Get Audio Quality |
| `com.apple.VoiceMemos.AudioQualityEntity-UpdatableEntity` | Edit Audio Quality |
| `com.apple.VoiceMemos.ChangeRecordingPlaybackSetting` | Change Recording Playback Setting |
| `com.apple.VoiceMemos.ClearDeletedEntity` | Get Clear Deleted |
| `com.apple.VoiceMemos.ClearDeletedEntity-UpdatableEntity` | Edit Clear Deleted |
| `com.apple.VoiceMemos.CreateFolder` | Create Folder |
| `com.apple.VoiceMemos.DeleteFolder` | Delete Folders |
| `com.apple.VoiceMemos.DeleteRecording` | Delete Recordings |
| `com.apple.VoiceMemos.LocationBasedNamingEntity` | Get Location-based Naming |
| `com.apple.VoiceMemos.LocationBasedNamingEntity-UpdatableEntity` | Edit Location-based Naming |
| `com.apple.VoiceMemos.OpenFolder` | Open Folder |
| `com.apple.VoiceMemos.OpenResetAnalyticsIdentifierEntity` | Open Reset Identifier |
| `com.apple.VoiceMemos.PlaybackVoiceMemoIntent` | Play Recording |
| `com.apple.VoiceMemos.RCCombineRecordings` | Combine Recordings |
| `com.apple.VoiceMemos.RCControlCenterToggleRecording` | CONTROL_CENTER_TOGGLE_RECORDING_INTENT_TITLE |
| `com.apple.VoiceMemos.RCImportRecording` | Import Recording |
| `com.apple.VoiceMemos.RCRecordingEntity` | Find Recordings |
| `com.apple.VoiceMemos.RecordVoiceMemoIntent` | Create Recording |
| `com.apple.VoiceMemos.ResetAnalyticsIdentifierEntity` | Get Reset Identifier |
| `com.apple.VoiceMemos.SearchRecordings` | Search in Voice Memos |
| `com.apple.VoiceMemos.SelectRecording` | Select Recording |
| `com.apple.VoiceMemos.StopRecording` | Stop Recording |
| `com.apple.VoiceMemos.ToggleRecording` | Voice Memo |
| `com.apple.VoiceMemos.WFAppSettingEntityUpdaterAction` | Change Voice Memos Settings |

### Shortcuts (23 actions)


| Identifier | Title |
|------------|-------|
| `com.apple.VoiceMemos.WFGetAppSettingAction` | Get Voice Memos Settings |
| `com.apple.news.WFGetAppSettingAction` | Get News Settings |
| `com.apple.shortcuts.AddShortcutToHomeScreenAction` | Add Shortcut to Home Screen |
| `com.apple.shortcuts.ChangeShortcutIconAction` | Change Shortcut Icon |
| `com.apple.shortcuts.CreateFolderAction` | Create Folder |
| `com.apple.shortcuts.CreateShortcutiCloudLinkAction` | Create iCloud Link for Shortcut |
| `com.apple.shortcuts.CreateWorkflowAction` | Create Shortcut |
| `com.apple.shortcuts.DeleteWorkflowAction` | Delete Shortcuts |
| `com.apple.shortcuts.GetShortcutAttributesAction` | Get Shortcut Attributes |
| `com.apple.shortcuts.MoveShortcutToFolderAction` | Move Shortcut |
| `com.apple.shortcuts.OpenAppIntent` | Open App |
| `com.apple.shortcuts.OpenNavigationDestinationAction` | Open Folder |
| `com.apple.shortcuts.OpenShortcutsStaticDeepLinks` | Open Shortcuts Settings *(iOS-only — see Platform Availability)* |
| `com.apple.shortcuts.OpenWorkflowAction` | Open Shortcut |
| `com.apple.shortcuts.RenameShortcutAction` | Rename Shortcut |
| `com.apple.shortcuts.RunShortcutConfigurationIntent` | Shortcut |
| `com.apple.shortcuts.RunShortcutFromCollectionIntent` | Run Shortcut from Folder |
| `com.apple.shortcuts.RunShortcutIntent` | Run Shortcut |
| `com.apple.shortcuts.SearchActionDrawerAction` | Search Shortcuts Actions |
| `com.apple.shortcuts.SearchShortcutsAction` | Search in Shortcuts |
| `com.apple.shortcuts.SetShortcutAttributesAction` | Set Shortcut Attributes |
| `com.apple.shortcuts.ShortcutsFolderConfigurationIntent` | Shortcuts Folder |
| `com.apple.shortcuts.StopWorkflowAction` | Stop Shortcut |

### System Controls (52 actions)

Toggle and set system settings:

| Pattern | Description |
|---------|-------------|
| `Set*` | Set system setting |
| `Toggle*` | Toggle system setting |
| `Update*` | Update system setting value |

Examples:
- `com.apple.Home.SetAttributeValueIntent` - Set Attribute
- `com.apple.Home.ToggleAttributeIntent` - Toggle Attribute
- `com.apple.AddressBook.UpdateContactIntent` - Update Contact Details

### Data & Search (37 actions)

| Pattern | Description |
|---------|-------------|
| `Find*` | Find/search items |
| `Get*` | Get data |
| `Search*` | Search for content |

Examples:
- `com.apple.Safari.FindOnPage` - Find on Page
- `com.apple.Home.GetAttributeValueIntent` - Get Attribute
- `com.apple.AddressBook.SearchInContactsIntent` - Search in Contacts App

------------|-------|
| `OpenAboutSettingsStaticDeepLinks` | Open About |
| `OpenAirDropSettingsStaticDeepLinks` | Open AirDrop |
| `OpenAppleIDSettingsStaticDeepLinks` | Open Apple ID |
| `OpenBatterySettingsStaticDeepLinks` | Open Battery |
| `OpenBluetoothSettingsStaticDeepLinks` | Open Bluetooth |
| `OpenDisplaySettingsStaticDeepLinks` | Open Display |
| `OpenFamilySettingsStaticDeepLinks` | Open Family |
| `OpenFocusSettingsStaticDeepLinks` | Open Focus |
| `OpenGeneralSettingsStaticDeepLinks` | Open General |
| `OpenInternetAccountsSettingsStaticDeepLinks` | Open Internet Accounts |
| `OpenKeyboardSettingsStaticDeepLinks` | Open Keyboard |
| `OpenLanguageSettingsStaticDeepLinks` | Open Language |
| `OpenNetworkSettingsStaticDeepLinks` | Open Network |
| `OpenNotificationSettingsStaticDeepLinks` | Open Notifications |
| `OpenPasswordsSettingsStaticDeepLinks` | Open Passwords |
| `OpenPrivacySettingsStaticDeepLinks` | Open Privacy |
| `OpenScreenTimeSettingsStaticDeepLinks` | Open Screen Time |
| `OpenSecuritySettingsStaticDeepLinks` | Open Security |
| `OpenSiriSettingsStaticDeepLinks` | Open Siri |
| `OpenSoftwareUpdateSettingsStaticDeepLinks` | Open Software Update |
| `OpenSoundSettingsStaticDeepLinks` | Open Sound |
| `OpenStorageSettingsStaticDeepLinks` | Open Storage |
| `OpenTrackpadSettingsStaticDeepLinks` | Open Trackpad |
| `OpenWalletSettingsStaticDeepLinks` | Open Wallet |
| `OpenWiFiSettingsStaticDeepLinks` | Open WiFi |

### Accessibility (164 actions)

Accessibility settings and controls:

| Identifier Pattern | Description |
|-------------------|-------------|
| `OpenAccessibility*StaticDeepLinks` | Open specific accessibility pane |
| `UpdateAx*EntityValueIntent` | Update accessibility setting value |
| `ToggleAx*` | Toggle accessibility feature |

Examples:
- `OpenAccessibilityVoiceOverStaticDeepLinks` - Open VoiceOver
- `OpenAccessibilityZoomStaticDeepLinks` - Open Zoom
- `OpenAccessibilitySwitchControlStaticDeepLinks` - Open Switch Control
- `UpdateAxVoiceOverSpeakingRateEntityValueIntent` - Update VoiceOver rate
- `ToggleAxVoiceOverIntent` - Toggle VoiceOver

### Clock & Alarms (23 actions)

| Identifier | Description |
|------------|-------------|
| `CreateAlarmIntent` | Create new alarm |
| `DeleteAlarmIntent` | Delete alarm |
| `ToggleAlarmIntent` | Toggle alarm on/off |
| `CreateTimerIntent` | Create timer |
| `PauseTimerIntent` | Pause timer |
| `ResumeTimerIntent` | Resume timer |
| `CancelTimerIntent` | Cancel timer |
| `StartStopwatchIntent` | Start stopwatch |
| `ResetStopwatchIntent` | Reset stopwatch |

### Calendar (5 actions)

| Identifier | Description |
|------------|-------------|
| `CreateCalendarIntent` | Create calendar |
| `DeleteCalendarIntent` | Delete calendar |
| `OpenCalendarScreenIntent` | Open calendar view |
| `CloseCalendarScreenIntent` | Close calendar |

### Reminders (12 actions)

| Identifier | Description |
|------------|-------------|
| `CreateReminderListIntent` | Create reminder list |
| `DeleteReminderListIntent` | Delete reminder list |
| `OpenReminderListIntent` | Open reminder list |
| `OpenSmartReminderListIntent` | Open smart list |
| `CompleteReminderIntent` | Complete reminder |

### Notes (8 actions)

| Identifier | Description |
|------------|-------------|
| `CreateNoteFolderIntent` | Create folder |
| `DeleteNoteFolderIntent` | Delete folder |
| `CreateNoteTagIntent` | Create tag |
| `DeleteNoteTagIntent` | Delete tag |
| `AddTagsToNotesIntent` | Add tags to notes |
| `RemoveTagsFromNotesIntent` | Remove tags |
| `PinNotesIntent` | Pin notes |
| `FindNotesIntent` | Find notes |

### Safari (18 actions)

| Identifier | Description |
|------------|-------------|
| `CreateTabIntent` | Create new tab |
| `CreatePrivateTabIntent` | Create private tab |
| `CloseTabIntent` | Close tab |
| `CreateTabGroupIntent` | Create tab group |
| `OpenTabIntent` | Open tab |
| `OpenTabGroupIntent` | Open tab group |
| `FindBookmarksIntent` | Find bookmarks |
| `FindReadingListItemsIntent` | Find reading list |
| `FindTabsIntent` | Find tabs |
| `FindTabGroupsIntent` | Find tab groups |
| `ChangeReaderModeStateIntent` | Toggle reader mode |

### Home (4 actions)

| Identifier | Description |
|------------|-------------|
| `FindHomeIntent` | Find home |
| `FindHomeDeviceIntent` | Find device |
| `FindHomeSceneIntent` | Find scene |
| `ToggleHomeAccessoryIntent` | Toggle accessory |

### Photos (24 actions)

| Identifier | Description |
|------------|-------------|
| `CreateMemoryIntent` | Create memory |
| `OpenCameraIntent` | Open camera |
| `FindPhotosIntent` | Find photos |
| `FindAlbumsIntent` | Find albums |
| `CreateAlbumIntent` | Create album |

### Music (2 actions)

| Identifier | Description |
|------------|-------------|
| `RecognizeMusicIntent` | Shazam recognition |
| `PlayMusicIntent` | Play music |

### Writing Tools (3 actions)

| Identifier | Description |
|------------|-------------|
| `ProofreadIntent` | Proofread text |
| `RewriteIntent` | Rewrite text |
| `SummarizeIntent` | Summarize text |

### Voice Memos (10 actions)

| Identifier | Description |
|------------|-------------|
| `CreateVoiceMemoFolderIntent` | Create folder |
| `DeleteVoiceMemoFolderIntent` | Delete folder |
| `OpenVoiceMemoFolderIntent` | Open folder |
| `FindVoiceMemosIntent` | Find recordings |
| `PlayVoiceMemoIntent` | Play recording |
| `DeleteVoiceMemosIntent` | Delete recordings |

### Shortcuts (8 actions)

| Identifier | Description |
|------------|-------------|
| `CreateWorkflowIntent` | Create shortcut |
| `DeleteWorkflowIntent` | Delete shortcut |
| `CreateiCloudLinkIntent` | Create iCloud link |
| `SearchShortcutsIntent` | Search shortcuts |
| `RunShortcutIntent` | Run shortcut |

### System Controls (154 actions)

Toggle and set system settings:

| Pattern | Description |
|---------|-------------|
| `Set*ModeIntent` | Set mode (silent, low power, etc.) |
| `Toggle*Intent` | Toggle setting |
| `Update*EntityValueIntent` | Update setting value |
| `Set*SettingIntent` | Set specific setting |

Examples:
- `SetLowPowerModeIntent` - Set low power mode
- `SetAirplaneModeIntent` - Set airplane mode
- `ToggleBluetoothIntent` - Toggle Bluetooth
- `SetBrightnessIntent` - Set brightness
- `SetVolumeIntent` - Set volume

### Data & Search (21 actions)

| Pattern | Description |
|---------|-------------|
| `Find*Intent` | Find/search items |
| `Get*Intent` | Get data |
| `Search*Intent` | Search for content |

Examples:
- `FindSportsEventsIntent` - Find sports events
- `GetPhysicalActivityIntent` - Get physical activity
- `SearchFilesIntent` - Search files

---

## Complete AppIntent Identifier List

First-party AppIntent identifiers kept for iOS/iPadOS (full IDs):

### Open* (Settings Deep Links)
```
com.apple.AppStoreSettingsAppIntents.OpenAppStoreSettingsDeepLinkIntent, com.apple.Bridge.OpenAboutDeepLinks, com.apple.Bridge.OpenAccessibilityDeepLinks
com.apple.Bridge.OpenActionButtonDeepLinks, com.apple.Bridge.OpenAppViewDeepLinks, com.apple.Bridge.OpenAssistiveTouchDeepLinks
com.apple.Bridge.OpenCellularDeepLinks, com.apple.Bridge.OpenDisplayBrightnessDeepLinks, com.apple.Bridge.OpenEmergencySOSDeepLinks
com.apple.Bridge.OpenGeneralDeepLinks, com.apple.Bridge.OpenGesturesDeepLinks, com.apple.Bridge.OpenNotificationsDeepLinks
com.apple.Bridge.OpenPasscodeDeepLinks, com.apple.Bridge.OpenPrivacyDeepLinks, com.apple.Bridge.OpenSiriDeepLinks
com.apple.Bridge.OpenSmartStackDeepLinks, com.apple.Bridge.OpenSoundsAndHapticsDeepLinks, com.apple.Bridge.OpenVoiceOverDeepLinks
com.apple.Bridge.OpenZoomDeepLinks, com.apple.ClassKit.ClassKitAppIntents.OpenClassKitAppIntentsDeepLinks
com.apple.Fitness.OpenActivityRingIntent, com.apple.Fitness.OpenFitnessAppSettingsDeepLinksIntent, com.apple.Fitness.OpenFitnessPlusForYouIntent
com.apple.Fitness.OpenMindfulnessSessionIntent, com.apple.Fitness.OpenUnifiedWorkoutIntent, com.apple.GameCenter.Settings.DeviceExpertExtension.OpenGameCenterSettingsDeepLinks
com.apple.HealthStandaloneIntents.OpenHealthSettingsIntent, com.apple.Home.OpenURLInHomeIntent, com.apple.Maps.MapsSettingsAppIntents.OpenMapsSettingsDeepLink
com.apple.MobileSMS.OpenConversationIntent, com.apple.MobileSMS.OpenConversationListIntent, com.apple.MobileSMS.OpenMessageIntent
com.apple.Notes.OpenAccountLinkAction, com.apple.Notes.OpenAppLocationLinkAction, com.apple.Notes.OpenAttachmentLinkAction
com.apple.Notes.OpenChecklistItemLinkAction, com.apple.Notes.OpenFolderLinkAction, com.apple.Notes.OpenTableLinkAction
com.apple.Notes.OpenTagLinkAction, com.apple.Notes.OpenTopLevelFolderLinkAction, com.apple.Passbook.OpenOrdersIntent
com.apple.Passbook.OpenSavingsAccountEntity, com.apple.Passbook.OpenTransactionEntity, com.apple.Photos.OpenAlbumIntent
com.apple.Photos.OpenAssetIntent, com.apple.Photos.OpenDestinationIntent, com.apple.Photos.OpenMemoryCreationViewIntent
com.apple.Photos.OpenMemoryIntent, com.apple.Photos.OpenPersonIntent, com.apple.Preferences.OpenAirDropBringDevicesTogetherEntity
com.apple.Preferences.OpenAirDropReceivingModeEntity, com.apple.Preferences.OpenAirDropSettingsStaticLinks, com.apple.Preferences.OpenAirDropUseCellularDataEntity
com.apple.Preferences.OpenAmbientSettingsDeepLinks, com.apple.Preferences.OpenCameraSettingsDeepLinks, com.apple.Preferences.OpenContactsDynamicDeepLinks
com.apple.Preferences.OpenControlCenterDeepLinks, com.apple.Preferences.OpenDefaultAppsSettingsDeepLink, com.apple.Preferences.OpenDictionarySettingsDeepLinks
com.apple.Preferences.OpenDisplayAndBrightnessDeepLink, com.apple.Preferences.OpenFaceTimeSettingsDynamicDeepLinks, com.apple.Preferences.OpenFindMySettingsDeepLinks
com.apple.Preferences.OpenFocusSettingsDynamicDeepLinks, com.apple.Preferences.OpenFontSettingsStaticDeepLinks, com.apple.Preferences.OpenHomeScreenAndAppLibraryDeepLink
com.apple.Preferences.OpenMailSettingsDeepLink, com.apple.Preferences.OpenMobilePhoneSettingsDynamicDeepLinks, com.apple.Preferences.OpenMultitaskingAndGesturesDeepLink
com.apple.Preferences.OpenMusicSettingsDeepLink, com.apple.Preferences.OpenNotificationsSettingsDeepLinks, com.apple.Preferences.OpenPasswordManagerDeepLinks
com.apple.Preferences.OpenPasswordSettingsDeepLinks, com.apple.Preferences.OpenPhotosDeepLinks, com.apple.Preferences.OpenSafetyCheckDeepLinks
com.apple.Preferences.OpenScreenTimeDeepLinksIntent, com.apple.Preferences.OpenScreenshotServicesSettingsDeepLinkIntent, com.apple.Preferences.OpenSettingsCellularDeepLinks
com.apple.Preferences.OpenSettingsDeepLink, com.apple.Preferences.OpenSettingsSOSDeepLinks, com.apple.Preferences.OpenTVProviderDeepLinks
com.apple.Preferences.OpenTwentyFourHourTimeEntity, com.apple.Preferences.OpenWalletDeepLinksIntent, com.apple.Preferences.OpeniCloudCalendarSettingsDeepLinks
com.apple.Preferences.OpeniCloudMailSettingsDeepLinks, com.apple.Preview.OpenIntent, com.apple.Safari.OpenBookmark
com.apple.Safari.OpenBookmarkAssistantIntent, com.apple.Safari.OpenTab, com.apple.Safari.OpenTabGroup
com.apple.Safari.OpenTabGroupForFocus, com.apple.Safari.OpenView, com.apple.TransparencySettingsIntents.OpenTransparencyPublicVerificationCodeDeepLink
com.apple.TransparencySettingsIntents.OpenTransparencyStatusDeepLink, com.apple.VoiceMemos.OpenFolder, com.apple.VoiceMemos.OpenResetAnalyticsIdentifierEntity
com.apple.clock.OpenAlarmIntent, com.apple.clock.OpenTab, com.apple.clock.OpenTabIntent
com.apple.compass.CompassSettingsAppIntents.OpenCompassSettingsDeepLink, com.apple.donotdisturb.DoNotDisturbAppIntents.OpenFocusSettingsDynamicDeepLinks, com.apple.finder.OpenItemIntent
com.apple.iBooksX.OpenBookIntent, com.apple.iBooksX.OpenDefaultCollectionIntent, com.apple.iBooksX.OpenMostRecentBookIntent
com.apple.iBooksX.OpenSpecificBookIntent, com.apple.iBooksX.OpenTabBarItemIntent, com.apple.iBooksX.OpenTableOfContentsIntent
com.apple.iCal.OpenCalendarEditorIntent, com.apple.iCal.OpenCalendarViewIntent, com.apple.iCal.OpenDateIntent
com.apple.iCal.OpenEventDetailsIntent, com.apple.iCal.OpenEventEditorIntent, com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenApplication
com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenFile, com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenURL, com.apple.journal.OpenEntryEntityIntent
com.apple.journal.OpenJournalSettingsDeeplinks, com.apple.mail.OpenDraftIntent, com.apple.mail.OpenDraftURLIntent
com.apple.mail.OpenMessageURLIntent, com.apple.mobilecal.OpenSettingsCalendarStaticDeepLinks, com.apple.mobilesafari.OpenLinksInBackgroundEntity
com.apple.mobilesafari.OpenLinksInBackgroundEntity-UpdatableEntity, com.apple.mobilesafari.OpenSafariSettingDeepLinks, com.apple.news.OpenArticleIntent
com.apple.news.OpenFeedIntent, com.apple.news.OpenHistoryIntent, com.apple.news.OpenNewsSettingsAutomaticDownloadDynamicDeepLinks
com.apple.news.OpenNewsSettingsDynamicDeepLinks, com.apple.news.OpenRecipeIntent, com.apple.news.OpenSavedIntent
com.apple.news.OpenSavedRecipesIntent, com.apple.news.OpenStaticFeed, com.apple.omniSearch.SearchToolExtension.OpenFlightReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenGenericEventEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenHotelReservationEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenIDCardBusinessEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenIDCardPersonalEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenMediaEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenRestaurantReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenSearchSpotlightEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenTicketedShowEntityIntent, com.apple.omniSearch.SearchToolExtension.OpenTicketedTransportationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenVehicleReservationEntityIntent, com.apple.podcasts.OpenAppLocationAppIntent, com.apple.podcasts.OpenChannelAppIntent
com.apple.podcasts.OpenEpisodeAppIntent, com.apple.podcasts.OpenShowAppIntent, com.apple.reminders.OpenGroupAppIntent
com.apple.reminders.OpenIncludeDueTodayDeepLink, com.apple.reminders.OpenMuteNotificationsDeepLink, com.apple.reminders.OpenReminderAppIntent
com.apple.reminders.OpenRemindersSettingsDeepLink, com.apple.reminders.OpenSectionAppIntent, com.apple.reminders.OpenShowAsOverdueDeepLink
com.apple.reminders.OpenShowSuggestionsDeepLink, com.apple.reminders.OpenSmartListAppIntent, com.apple.reminders.OpenTagsAppIntent
com.apple.reminders.OpenTodayNotificationDeepLink, com.apple.shortcuts.OpenAppIntent, com.apple.shortcuts.OpenNavigationDestinationAction
com.apple.shortcuts.OpenShortcutsStaticDeepLinks, com.apple.shortcuts.OpenWorkflowAction, com.apple.siri.AssistantSettingsControls.OpenAlwaysPrintSiriResponseEntity
com.apple.siri.AssistantSettingsControls.OpenAlwaysShowSpeechEntity, com.apple.siri.AssistantSettingsControls.OpenAskSiriEntity, com.apple.siri.AssistantSettingsControls.OpenKeyboardShortcutEntity
com.apple.siri.AssistantSettingsControls.OpenSiriAndDictationHistoryEntity, com.apple.siri.AssistantSettingsControls.OpenSiriLanguageEntity, com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsAndPrivacyEntity
com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsAndPrivacyForAppEntity, com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsShowInAppEntity, com.apple.siri.AssistantSettingsControls.OpenSiriVoiceEntity
com.apple.siri.AssistantSettingsControls.OpenVoiceFeedbackToggleEntity, com.apple.springboard.OpenCamera, com.apple.stocks.OpenArticleIntent
com.apple.stocks.OpenBusinessNewsIntent, com.apple.stocks.OpenFeedIntent, com.apple.stocks.OpenHistoryIntent
com.apple.stocks.OpenRecipeIntent, com.apple.stocks.OpenSavedIntent, com.apple.stocks.OpenSavedRecipesIntent
com.apple.stocks.OpenStaticFeed, com.apple.stocks.OpenSymbolIntent, com.apple.stocks.OpenWatchlistIntent


com.apple.weather.OpenMoonIntent
com.apple.weather.OpenNotificationsConfigurationIntent, com.apple.weather.OpenSunriseSunsetIntent, com.apple.weather.OpenUnitsConfigurationIntent
com.apple.weather.OpenWeatherAirQualityIntent, com.apple.weather.OpenWeatherSpecificConditionIntent
```

### Create* (Creation Actions)
```
com.apple.AddressBook.CreateContactIntent, com.apple.Notes.CreateChecklistItemLinkAction, com.apple.Notes.CreateFolderLinkAction
com.apple.Notes.CreateNoteFromMarkdownLinkAction, com.apple.Notes.CreateTableLinkAction, com.apple.Notes.CreateTagLinkAction
com.apple.Photos.CreateAlbumIntent, com.apple.Photos.CreateAssetsIntent, com.apple.Safari.CreateNewBookmark
com.apple.Safari.CreateNewTab, com.apple.Safari.CreateNewTabGroup, com.apple.Safari.CreateNewWindow
com.apple.Safari.CreateTabAssistantIntent, com.apple.VoiceMemos.CreateFolder, com.apple.finder.CreateFolderIntent
com.apple.iCal.CreateCalendarIntent, com.apple.iCal.CreateEventIntent, com.apple.iCal.CreateEventIntent_v0
com.apple.journal.CreateEntryAudioIntent, com.apple.journal.CreateEntryIntent, com.apple.mobilenotes.CreateTagLinkAction
com.apple.reminders.CreateCustomSmartListAppIntent, com.apple.reminders.CreateGroupAppIntent, com.apple.reminders.CreateQuickReminderIntent
com.apple.reminders.CreateSectionAppIntent, com.apple.shortcuts.CreateFolderAction, com.apple.shortcuts.CreateShortcutiCloudLinkAction
com.apple.shortcuts.CreateWorkflowAction
```

### Toggle* (Toggle Actions)
```
com.apple.Home.ToggleAttributeIntent, com.apple.Home.ToggleControlConfigurationIntent, com.apple.Home.ToggleIntent
com.apple.ShortcutsActions.ToggleCellularPlanAction, com.apple.Spotlight.ToggleSpotlightIntent, com.apple.VoiceMemos.ToggleRecording
com.apple.news.ToggleAudioPlaybackIntent, com.apple.springboard.ToggleFlashlight
```

### Set* (Setting Actions)
```
com.apple.Bridge.SettingsNavigationEventDonationIntent, com.apple.DocumentsApp.SetFilenameExtensionVisibilityIntent, com.apple.DocumentsApp.SetGroupingModeIntent
com.apple.Fitness.SetFitnessGoalIntent, com.apple.Fitness.SetFitnessGoalScheduleIntent, com.apple.Fitness.SetWorkoutEffortIntent
com.apple.Home.SetAttributeValueIntent, com.apple.Notes.SetAttachmentSizeLinkAction, com.apple.Notes.SetChecklistItemCheckedLinkActionv2
com.apple.Notes.SetParagraphStyleLinkAction, com.apple.Passbook.SetDefaultCardIntent, com.apple.Photos.SetApertureIntent
com.apple.Photos.SetAudioMixIntent, com.apple.Photos.SetExposureIntent, com.apple.Photos.SetPlaybackRateIntent
com.apple.Photos.SetSaturationIntent, com.apple.Photos.SetWarmthIntent, com.apple.Preferences.SettingsCellularDeepLinks
com.apple.Preferences.SettingsDeepLink, com.apple.Preferences.SettingsNavigationEventDonationIntent, com.apple.ShortcutsActions.SetDataRoamingAction
com.apple.ShortcutsActions.SetDefaultCellularPlanAction, com.apple.ShortcutsActions.SetSilentModeAction, com.apple.ShortcutsActions.SetVoiceDataModeAction
com.apple.controlcenter.SetDarkModeEnabledIntent, com.apple.controlcenter.SetNightShiftEnabledIntent, com.apple.controlcenter.SetTrueToneEnabledIntent
com.apple.dock.SetDockAutoHideEnabledIntent, com.apple.donotdisturb.DoNotDisturbAppIntents.SetFocusState, com.apple.homed.SetPersonalContentSettingIntent
com.apple.iCal.SetCalendarFocusConfiguration, com.apple.mail.SetMailMessageIsRead, com.apple.mail.SetReadLaterIntent
com.apple.mobilecal.SettingsAllDayDefaultAlertTimesEntity, com.apple.mobilecal.SettingsAllDayDefaultAlertTimesEntity-UpdatableEntity, com.apple.mobilecal.SettingsAlternateCalendarEntity
com.apple.mobilecal.SettingsAlternateCalendarEntity-UpdatableEntity, com.apple.mobilecal.SettingsBirthdaysDefaultAlertTimesEntity, com.apple.mobilecal.SettingsBirthdaysDefaultAlertTimesEntity-UpdatableEntity
com.apple.mobilecal.SettingsDurationForNewEventsEntity, com.apple.mobilecal.SettingsDurationForNewEventsEntity-UpdatableEntity, com.apple.mobilecal.SettingsEventsDefaultAlertTimesEntity
com.apple.mobilecal.SettingsEventsDefaultAlertTimesEntity-UpdatableEntity, com.apple.mobilecal.SettingsShowInviteeDeclinesEntity, com.apple.mobilecal.SettingsShowInviteeDeclinesEntity-UpdatableEntity
com.apple.mobilecal.SettingsShowLocationSuggestionsEntity, com.apple.mobilecal.SettingsShowLocationSuggestionsEntity-UpdatableEntity, com.apple.mobilecal.SettingsShowWeekNumbersEntity
com.apple.mobilecal.SettingsShowWeekNumbersEntity-UpdatableEntity, com.apple.mobilecal.SettingsStartWeekOnEntity, com.apple.mobilecal.SettingsStartWeekOnEntity-UpdatableEntity
com.apple.mobilecal.SettingsSyncDurationsEntity, com.apple.mobilecal.SettingsSyncDurationsEntity-UpdatableEntity, com.apple.mobilecal.SettingsTimeToLeaveEntity
com.apple.mobilecal.SettingsTimeToLeaveEntity-UpdatableEntity, com.apple.mobilecal.SettingsWeekViewStartsOnTodayEntity, com.apple.mobilecal.SettingsWeekViewStartsOnTodayEntity-UpdatableEntity
com.apple.shortcuts.SetShortcutAttributesAction, com.apple.springboard.SetAppearanceStyleIntent, com.apple.springboard.SetFlashlightIntent
com.apple.springboard.SetSilentModeIntent, com.apple.wallpaper.agent.SetWallpaperIntent
com.apple.wallpaper.agent.SetWallpaperPhotoIntent, com.apple.weather.SetDistanceUnitIntent, com.apple.weather.SetPrecipitationUnitIntent
com.apple.weather.SetPressureUnitIntent, com.apple.weather.SetTemperatureUnitIntent, com.apple.weather.SetWindUnitIntent
```

### Find* (Search Actions)
```
com.apple.Safari.FindOnPage, com.apple.intelligenceplatform.IntelligencePlatform.IntelligencePlatformDataActionsAppIntentsExtension.FindSportsEvents
```

### All AppIntent Identifiers (full IDs)
```
com.apple.AddressBook.ContactEntity
com.apple.AddressBook.CreateContactIntent
com.apple.AddressBook.DeleteContactIntent
com.apple.AddressBook.FetchContactAvatarIntent
com.apple.AddressBook.FetchContactIntent
com.apple.AddressBook.SearchInContactsIntent
com.apple.AddressBook.UpdateContactIntent
com.apple.AddressBook.ViewContactCardIntent
com.apple.AppKit.FetchIntelligenceCommands
com.apple.AppKit.InsertIntelligenceText
com.apple.AppKit.RunIntelligenceCommand
com.apple.AppKit.RunIntelligenceCommandForKey
com.apple.AppKit.WindowTabActivateIntent
com.apple.AppKit.WindowTabEntity
com.apple.AppKit.WritingToolsComposeIntent
com.apple.AppKit.WritingToolsProofreadIntent
com.apple.AppKit.WritingToolsRewriteIntent
com.apple.AppStore.SystemSearchIntent
com.apple.GameCenter.Settings.DeviceExpertExtension.OpenGameCenterSettingsDeepLinks
com.apple.GenerativePlaygroundApp.GenerateImageIntent
com.apple.Home.ActivateSceneIntent
com.apple.Home.AutomateAttributeValueIntent
com.apple.Home.AutomateSceneIntent
com.apple.Home.CameraClipEntity
com.apple.Home.DeltaAttributeValueIntent
com.apple.Home.DeviceEntity
com.apple.Home.ErrorIntent
com.apple.Home.ForecastWidgetConfiguration
com.apple.Home.GetAttributeValueIntent
com.apple.Home.GetDeviceInfoIntent
com.apple.Home.HistoricalUsageWidgetConfiguration
com.apple.Home.HomeAppIntentsExtensionTestAppIntent
com.apple.Home.HomeEntity
com.apple.Home.HomeSingleTileConfigurationIntent
com.apple.Home.HomeXLModuleConfigurationIntent
com.apple.Home.OpenURLInHomeIntent
com.apple.Home.RecommendedItemIntent
com.apple.Home.RoomEntity
com.apple.Home.SceneEntity
com.apple.Home.SecureToggleIntent
com.apple.Home.SelectedHomeEntity
com.apple.Home.SetAttributeValueIntent
com.apple.Home.ShowDeviceResultIntent
com.apple.Home.ShowErrorIntent
com.apple.Home.ShowNavigationIntent
com.apple.Home.ShowSceneResultIntent
com.apple.Home.TileControlAction
com.apple.Home.ToggleAttributeIntent
com.apple.Home.ToggleControlConfigurationIntent
com.apple.Home.ToggleIntent
com.apple.Home.UtilityRateInfoWidgetConfiguration
com.apple.Home.ZoneEntity
com.apple.HydraUSDAppIntents.ConvertToUSDZ
com.apple.Magnifier.DescribeThisIntent
com.apple.Magnifier.DetectDoorsIntent
com.apple.Magnifier.DetectFurnitureIntent
com.apple.Magnifier.DetectPeopleIntent
com.apple.Magnifier.DetectTextIntent
com.apple.Magnifier.MagnifierIntent
com.apple.Magnifier.PointAndSpeakIntent
com.apple.Magnifier.ReaderModeIntent
com.apple.Magnifier.StartDetectionTypeIntent
com.apple.MobileSMS.ChangeFilterModeIntent
com.apple.MobileSMS.ConversationEntity
com.apple.MobileSMS.ConversationListFocusFilterAction
com.apple.MobileSMS.DeleteConversationIntent
com.apple.MobileSMS.DeleteMessageIntent
com.apple.MobileSMS.FetchConversationIdentifierIntent
com.apple.MobileSMS.FetchDowntimeConversationListIntent
com.apple.MobileSMS.FetchMutedConversationListIntent
com.apple.MobileSMS.MarkConversationAsUnreadIntent
com.apple.MobileSMS.MessageEntity
com.apple.MobileSMS.MuteConversationIntent
com.apple.MobileSMS.OpenConversationIntent
com.apple.MobileSMS.OpenConversationListIntent
com.apple.MobileSMS.OpenMessageIntent
com.apple.MobileSMS.RemoveTapbackIntent
com.apple.MobileSMS.SendMessageReactionIntent
com.apple.MobileSMS.SendReplyIntent
com.apple.MobileSMS.SendTapbackIntent
com.apple.Notes.AddFileAttachmentLinkAction
com.apple.Notes.AddLinkAttachmentLinkAction
com.apple.Notes.AddOrRemoveNoteLockLinkAction
com.apple.Notes.AddTagsToNotesLinkAction
com.apple.Notes.AppendMarkdownToNoteLinkAction
com.apple.Notes.ApplyFormattingLinkAction
com.apple.Notes.AttachmentEntity
com.apple.Notes.ChangeFolderSettingLinkAction
com.apple.Notes.ChangeSettingLinkAction
com.apple.Notes.ChangeTagSelectionIntent
com.apple.Notes.CloseAppLocationLinkAction
com.apple.Notes.CloseNoteLinkAction
com.apple.Notes.CreateChecklistItemLinkAction
com.apple.Notes.CreateFolderLinkAction
com.apple.Notes.CreateNoteFromMarkdownLinkAction
com.apple.Notes.CreateTableLinkAction
com.apple.Notes.CreateTagLinkAction
com.apple.Notes.DeleteAttachmentsLinkAction
com.apple.Notes.DeleteChecklistItemsLinkAction
com.apple.Notes.DeleteFoldersLinkAction
com.apple.Notes.DeleteNotesLinkAction
com.apple.Notes.DeleteTablesLinkAction
com.apple.Notes.DeleteTagsLinkAction
com.apple.Notes.GetLinkedNotesLinkAction
com.apple.Notes.InsertAllMentionLinkAction
com.apple.Notes.InsertMentionLinkAction
com.apple.Notes.InsertNoteLinkLinkAction
com.apple.Notes.MoveNotesToFolderLinkAction
com.apple.Notes.OpenAccountLinkAction
com.apple.Notes.OpenAppLocationLinkAction
com.apple.Notes.OpenAttachmentLinkAction
com.apple.Notes.OpenChecklistItemLinkAction
com.apple.Notes.OpenFolderLinkAction
com.apple.Notes.OpenTableLinkAction
com.apple.Notes.OpenTagLinkAction
com.apple.Notes.OpenTopLevelFolderLinkAction
com.apple.Notes.PinNotesLinkAction
com.apple.Notes.QuickNoteIntent
com.apple.Notes.RemoveTagsFromNotesLinkAction
com.apple.Notes.RenameFolderLinkAction
com.apple.Notes.ReplaceSelectionLinkAction
com.apple.Notes.SetAttachmentSizeLinkAction
com.apple.Notes.SetChecklistItemCheckedLinkActionv2
com.apple.Notes.SetParagraphStyleLinkAction
com.apple.Notes.ShowNotesAppSearchResultsLinkAction
com.apple.Notes.ShowQuickNoteIntent
com.apple.Notes.StartRecordingLinkAction
com.apple.Notes.TableEntity
com.apple.PeopleViewService.SelectPersonIntent
com.apple.PeopleViewService.URLAppIntent
com.apple.Photos.AddAssetsToAlbumIntent
com.apple.Photos.ApplyFilterIntent
com.apple.Photos.ApplyStyleIntent
com.apple.Photos.CleanupIntent
com.apple.Photos.CopyEditsIntent
com.apple.Photos.CreateAlbumIntent
com.apple.Photos.CreateAssetsIntent
com.apple.Photos.CropIntent
com.apple.Photos.DeleteAlbumsIntent
com.apple.Photos.DeleteAssetsIntent
com.apple.Photos.DuplicateAssetsIntent
com.apple.Photos.EditAssetIntent
com.apple.Photos.EnableDepthIntent
com.apple.Photos.EnhanceIntent
com.apple.Photos.FavoriteAssetsIntent
com.apple.Photos.FavoriteMemoriesIntent
com.apple.Photos.FavoritePeopleIntent
com.apple.Photos.FilterLibraryIntent
com.apple.Photos.HideAssetsIntent
com.apple.Photos.HidePeopleIntent
com.apple.Photos.MarkupIntent
com.apple.Photos.MoveAssetsToPersonalLibraryIntent
com.apple.Photos.MoveAssetsToSharedLibraryIntent
com.apple.Photos.OpenAlbumIntent
com.apple.Photos.OpenAssetIntent
com.apple.Photos.OpenDestinationIntent
com.apple.Photos.OpenMemoryCreationViewIntent
com.apple.Photos.OpenMemoryIntent
com.apple.Photos.OpenPersonIntent
com.apple.Photos.PLPhotosReliveWidgetConfigurationIntent
com.apple.Photos.PasteEditsIntent
com.apple.Photos.PhotosAddAssetsToAlbumAssistantIntent
com.apple.Photos.PhotosCleanupPhotoAssistantIntent
com.apple.Photos.PhotosCopyEditsAssistantIntent
com.apple.Photos.PhotosCreateAlbumAssistantIntent
com.apple.Photos.PhotosCreateAssetsAssistantIntent
com.apple.Photos.PhotosCropAssistantIntent
com.apple.Photos.PhotosDeleteAlbumsAssistantIntent
com.apple.Photos.PhotosDeleteAssetsAssistantIntent
com.apple.Photos.PhotosDuplicateAssetsAssistantIntent
com.apple.Photos.PhotosPasteEditsAssistantIntent
com.apple.Photos.PhotosReliveWidgetFeaturedConfiguration
com.apple.Photos.PhotosRemoveAssetsFromAlbumAssistantIntent
com.apple.Photos.PhotosSearchAssistantIntent
com.apple.Photos.PhotosSetDepthAssistantIntent
com.apple.Photos.PhotosSetExposureAssistantIntent
com.apple.Photos.PhotosSetFilterAssistantIntent
com.apple.Photos.PhotosSetRotationAssistantIntent
com.apple.Photos.PhotosSetSaturationAssistantIntent
com.apple.Photos.PhotosSetWarmthAssistantIntent
com.apple.Photos.PhotosStraightenAssistantIntent
com.apple.Photos.PhotosToggleDepthAssistantIntent
com.apple.Photos.PhotosToggleSuggestedEditsAssistantIntent
com.apple.Photos.PhotosUpdateAlbumAssistantIntent
com.apple.Photos.PhotosUpdateAssetAssistantIntent
com.apple.Photos.PhotosUpdateRecognizedPersonAssistantIntent
com.apple.Photos.RemoveAssetsFromAlbumIntent
com.apple.Photos.RenameAlbumIntent
com.apple.Photos.RenamePersonIntent
com.apple.Photos.RevealAlbumsIntent
com.apple.Photos.RevealAssetsIntent
com.apple.Photos.RotateIntent
com.apple.Photos.SetApertureIntent
com.apple.Photos.SetAudioMixIntent
com.apple.Photos.SetExposureIntent
com.apple.Photos.SetPlaybackRateIntent
com.apple.Photos.SetSaturationIntent
com.apple.Photos.SetWarmthIntent
com.apple.Photos.StraightenIntent
com.apple.Preview.AutoEnhanceIntent
com.apple.Preview.BookmarkIntent
com.apple.Preview.CloseIntent
com.apple.Preview.DeletePageIntent
com.apple.Preview.DocumentEntity
com.apple.Preview.ExportIntent
com.apple.Preview.FlipIntent
com.apple.Preview.GetPagesIntent
com.apple.Preview.InsertPageIntent
com.apple.Preview.OpenIntent
com.apple.Preview.RemoveBackgroundIntent
com.apple.Preview.ResizeIntent
com.apple.Preview.RevealDocumentIntent
com.apple.Preview.RevealPageIntent
com.apple.Preview.RotateIntent
com.apple.Preview.RotatePageIntent
com.apple.Preview.SaveIntent
com.apple.Preview.SearchIntent
com.apple.Safari.BookmarkEntity
com.apple.Safari.BookmarkTabIntent
com.apple.Safari.BookmarkURLIntent
com.apple.Safari.CloseTab
com.apple.Safari.CloseTabsAssistantIntent
com.apple.Safari.CloseView
com.apple.Safari.CloseWindowsIntent
com.apple.Safari.CreateNewBookmark
com.apple.Safari.CreateNewTab
com.apple.Safari.CreateNewTabGroup
com.apple.Safari.CreateNewWindow
com.apple.Safari.CreateTabAssistantIntent
com.apple.Safari.DeleteBookmarks
com.apple.Safari.DeleteTabGroups
com.apple.Safari.FindOnPage
com.apple.Safari.LoadURLInTab
com.apple.Safari.MoveTabsToTabGroup
com.apple.Safari.MoveTabsToWindowIntent
com.apple.Safari.OpenBookmark
com.apple.Safari.OpenBookmarkAssistantIntent
com.apple.Safari.OpenTab
com.apple.Safari.OpenTabGroup
com.apple.Safari.OpenTabGroupForFocus
com.apple.Safari.OpenView
com.apple.Safari.QuickWebsiteSearchIntent
com.apple.Safari.QuickWebsiteSearchProviderEntity
com.apple.Safari.SearchTabs
com.apple.Safari.ShowWindowIntent
com.apple.Safari.TabEntity
com.apple.Safari.TabGroupEntity
com.apple.Safari.WindowEntity
com.apple.ShortcutsActions.CellularPlanEntity
com.apple.ShortcutsActions.GetOrientationAction
com.apple.ShortcutsActions.GetPhysicalActivity
com.apple.ShortcutsActions.PlayMusicTopHitAction
com.apple.ShortcutsActions.PlayPodcastTopHitAction
com.apple.ShortcutsActions.ResetCellularDataStatisticsAction
com.apple.ShortcutsActions.SetDataRoamingAction
com.apple.ShortcutsActions.SetDefaultCellularPlanAction
com.apple.ShortcutsActions.SetSilentModeAction
com.apple.ShortcutsActions.SetVoiceDataModeAction
com.apple.ShortcutsActions.ShowControlCenterAction
com.apple.ShortcutsActions.StartCallTopHitAction
com.apple.ShortcutsActions.StartFaceTimeAudioCallTopHitAction
com.apple.ShortcutsActions.StartFaceTimeCallTopHitAction
com.apple.ShortcutsActions.StartFaceTimeVideoCallTopHitAction
com.apple.ShortcutsActions.TimeMachineAction
com.apple.ShortcutsActions.ToggleCellularPlanAction
com.apple.ShortcutsActions.TranscribeAudioAction
com.apple.Spotlight.ClearSpotlightIntent
com.apple.Spotlight.SearchFieldEntity
com.apple.Spotlight.SearchSpotlightIntent
com.apple.Spotlight.SearchSpotlightIntentInternal
com.apple.Spotlight.SearchUIContinuationIntent
com.apple.Spotlight.SearchUIOpenKnowledgeIntent
com.apple.Spotlight.ToggleSpotlightIntent
com.apple.TransparencySettingsIntents.OpenTransparencyPublicVerificationCodeDeepLink
com.apple.TransparencySettingsIntents.OpenTransparencyStatusDeepLink
com.apple.TransparencySettingsIntents.TransparencyPublicVerificationCodeEntity
com.apple.TransparencySettingsIntents.TransparencySettingsIntents
com.apple.TransparencySettingsIntents.TransparencyStatusEntity
com.apple.VoiceMemos.AudioQualityEntity
com.apple.VoiceMemos.AudioQualityEntity-UpdatableEntity
com.apple.VoiceMemos.ChangeRecordingPlaybackSetting
com.apple.VoiceMemos.ClearDeletedEntity
com.apple.VoiceMemos.ClearDeletedEntity-UpdatableEntity
com.apple.VoiceMemos.CreateFolder
com.apple.VoiceMemos.DeleteFolder
com.apple.VoiceMemos.DeleteRecording
com.apple.VoiceMemos.LocationBasedNamingEntity
com.apple.VoiceMemos.LocationBasedNamingEntity-UpdatableEntity
com.apple.VoiceMemos.OpenFolder
com.apple.VoiceMemos.OpenResetAnalyticsIdentifierEntity
com.apple.VoiceMemos.PlaybackVoiceMemoIntent
com.apple.VoiceMemos.RCCombineRecordings
com.apple.VoiceMemos.RCControlCenterToggleRecording
com.apple.VoiceMemos.RCImportRecording
com.apple.VoiceMemos.RCRecordingEntity
com.apple.VoiceMemos.RecordVoiceMemoIntent
com.apple.VoiceMemos.ResetAnalyticsIdentifierEntity
com.apple.VoiceMemos.SearchRecordings
com.apple.VoiceMemos.SelectRecording
com.apple.VoiceMemos.StopRecording
com.apple.VoiceMemos.ToggleRecording
com.apple.VoiceMemos.WFAppSettingEntityUpdaterAction
com.apple.VoiceMemos.WFGetAppSettingAction
com.apple.WindowManager.AppExposeAction
com.apple.WindowManager.CornersTileAction
com.apple.WindowManager.MissionControlAction
com.apple.WindowManager.ShowDesktopAction
com.apple.WindowManager.StageManagerToggleIntent
com.apple.WindowManager.ThreeUpTileAction
com.apple.WindowManager.TwoUpTileAction
com.apple.WritingTools.WritingToolsAppIntentsExtension.AdjustToneIntent
com.apple.WritingTools.WritingToolsAppIntentsExtension.FormatListIntent
com.apple.WritingTools.WritingToolsAppIntentsExtension.FormatTableIntent
com.apple.WritingTools.WritingToolsAppIntentsExtension.ProofreadIntent
com.apple.WritingTools.WritingToolsAppIntentsExtension.RewriteTextIntent
com.apple.WritingTools.WritingToolsAppIntentsExtension.SummarizeTextIntent
com.apple.calculator.LaunchCalculatorOpenIntent
com.apple.clock.AddWorldClockIntent
com.apple.clock.CancelTimerIntent
com.apple.clock.DeleteAlarmIntent
com.apple.clock.GetCurrentTimerDetailsIntent
com.apple.clock.GetTimeForCityIntent
com.apple.clock.LapStopwatchIntent
com.apple.clock.OpenAlarmIntent
com.apple.clock.OpenTab
com.apple.clock.OpenTabIntent
com.apple.clock.PauseTimerIntent
com.apple.clock.RemoveWorldClockIntent
com.apple.clock.ResetStopwatchIntent
com.apple.clock.ResumeTimerIntent
com.apple.clock.StartStopwatchIntent
com.apple.clock.StopStopwatchIntent
com.apple.controlcenter.DisplaySleepIntent
com.apple.controlcenter.LockScreenIntent
com.apple.controlcenter.ScreenSaverIntent
com.apple.controlcenter.SetDarkModeEnabledIntent
com.apple.controlcenter.SetNightShiftEnabledIntent
com.apple.controlcenter.SetTrueToneEnabledIntent
com.apple.dock.SetDockAutoHideEnabledIntent
com.apple.donotdisturb.DoNotDisturbAppIntents.FocusEntity
com.apple.donotdisturb.DoNotDisturbAppIntents.OpenFocusSettingsDynamicDeepLinks
com.apple.donotdisturb.DoNotDisturbAppIntents.SetFocusState
com.apple.finder.CompressItemsIntent
com.apple.finder.CopyItemsIntent
com.apple.finder.CreateFolderIntent
com.apple.finder.DuplicateItemsIntent
com.apple.finder.GetInfoIntent
com.apple.finder.GetLocationIntent
com.apple.finder.GetSelectedItemsIntent
com.apple.finder.GoToEnclosingFolderIntent
com.apple.finder.GoToFolderIntent
com.apple.finder.GoToLocationIntent
com.apple.finder.MoveItemsIntent
com.apple.finder.OpenItemIntent
com.apple.finder.RenameItemIntent
com.apple.finder.RevealItemsIntent
com.apple.finder.SearchInBrowserIntent
com.apple.finder.TrashItemsIntent
com.apple.findmy.FriendSelectorIntent
com.apple.findmy.Intent
com.apple.findmy.ItemEntity
com.apple.findmy.ItemSelectorIntent
com.apple.findmy.PersonEntity
com.apple.findmy.WidgetItemEntity
com.apple.findmy.WidgetPersonEntity
com.apple.freeform.CRLAddItemToBoardIntent
com.apple.freeform.CRLAddStickyNoteToBoardIntent
com.apple.freeform.CRLAddTextToBoardIntent
com.apple.freeform.CRLChangeBoardCanvasGridIntent
com.apple.freeform.CRLChangeBoardObjectConnectorsIntent
com.apple.freeform.CRLChangeSelectionColorIntent
com.apple.freeform.CRLChangeSelectionFontSizeIntent
com.apple.freeform.CRLChangeSelectionFontStyleIntent
com.apple.freeform.CRLCreateBoardIntent
com.apple.freeform.CRLDeleteBoardIntent
com.apple.freeform.CRLFavoriteBoardIntent_v2
com.apple.freeform.CRLInsertFilesToBoardIntent
com.apple.freeform.CRLInsertPhotosToBoardIntent
com.apple.freeform.CRLInsertShapeToBoardIntent
com.apple.freeform.CRLInsertTextToBoardIntent
com.apple.freeform.CRLInsertURLToBoardIntent
com.apple.freeform.CRLOpenBoardIntent
com.apple.freeform.CRLRenameBoardIntent
com.apple.freeform.CRLResizeSelectionFontIntent
com.apple.freeform.CRLResizeSelectionFontIntent_v2
com.apple.freeform.CRLUpdateBoardIntent
com.apple.freeform.CRLUtilitiesIntent
com.apple.freeform.CRLiOSCreateBoardIntent
com.apple.freeform.CRLiOSOpenBoardIntent
com.apple.generativeassistanttools.GenerativeAssistantExtension.GenerateKnowledgeResponseIntent
com.apple.generativeassistanttools.GenerativeAssistantExtension.GenerateRichContentFromMediaIntent
com.apple.generativeassistanttools.GenerativeAssistantExtension.GenerateRichContentIntent
com.apple.generativeassistanttools.GenerativeAssistantExtension.PrewarmGenerativeAssistantExtensionIntent
com.apple.helpviewer.CollectionOpenIntent
com.apple.homed.SetPersonalContentSettingIntent
com.apple.iBooksX.AudiobookSleepTimerIntent
com.apple.iBooksX.BookAppEntity
com.apple.iBooksX.BookReaderChangeThemeIntent
com.apple.iBooksX.BookReaderNavigatePageInBookIntent
com.apple.iBooksX.BookReaderNavigatePagesIntent
com.apple.iBooksX.BookSettingsEntity
com.apple.iBooksX.BookSettingsEntity-UpdatableEntity
com.apple.iBooksX.ChangeFontSizeIntent
com.apple.iBooksX.CloseBookIntent
com.apple.iBooksX.DeepLinkIntent
com.apple.iBooksX.DefaultCollectionEntity
com.apple.iBooksX.OpenBookIntent
com.apple.iBooksX.OpenDefaultCollectionIntent
com.apple.iBooksX.OpenMostRecentBookIntent
com.apple.iBooksX.OpenSpecificBookIntent
com.apple.iBooksX.OpenTabBarItemIntent
com.apple.iBooksX.OpenTableOfContentsIntent
com.apple.iBooksX.PauseCurrentAudiobookIntent
com.apple.iBooksX.PlayAudiobookIntent
com.apple.iBooksX.PlayMostRecentAudiobookIntent
com.apple.iBooksX.PlaySpecificAudiobookIntent
com.apple.iBooksX.SearchBooksAppIntent
com.apple.iBooksX.SearchBooksIntent
com.apple.iBooksX.UpdateBookSettingsIntent
com.apple.iCal.CreateCalendarIntent
com.apple.iCal.CreateEventIntent
com.apple.iCal.CreateEventIntent_v0
com.apple.iCal.DeleteCalendarsIntent
com.apple.iCal.DeleteEventIntent
com.apple.iCal.DeleteEventIntent_v0
com.apple.iCal.EditEventIntent
com.apple.iCal.EditEventIntent_v0
com.apple.iCal.EmailAttendeesIntent
com.apple.iCal.EmailOrganizerIntent
com.apple.iCal.EventEntity
com.apple.iCal.FetchTransferableEventByURLIntent
com.apple.iCal.FetchTransferableEventsInRangeIntent
com.apple.iCal.HighlightEventIntent
com.apple.iCal.InboxItemEntity
com.apple.iCal.JoinEventIntent
com.apple.iCal.ListEventsIntent
com.apple.iCal.OpenCalendarEditorIntent
com.apple.iCal.OpenCalendarViewIntent
com.apple.iCal.OpenDateIntent
com.apple.iCal.OpenEventDetailsIntent
com.apple.iCal.OpenEventEditorIntent
com.apple.iCal.RespondToInboxItemIntent
com.apple.iCal.SetCalendarFocusConfiguration
com.apple.iCal.TransferableCalendarEntity
com.apple.iCal.TransferableSourceEntity
com.apple.iWork.Keynote.KNDocumentBackgroundExportIntent
com.apple.iWork.Keynote.KNNewDocumentIntent
com.apple.iWork.Numbers.TNDocumentBackgroundExportIntent
com.apple.iWork.Numbers.TNNewDocumentIntent
com.apple.iWork.Pages.TPDocumentBackgroundExportIntent
com.apple.iWork.Pages.TPNewDocumentIntent
com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenApplication
com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenFile
com.apple.intelligenceflow.IntelligenceFlowAppIntentsExtension.OpenURL
com.apple.intelligenceplatform.IntelligencePlatform.IntelligencePlatformDataActionsAppIntentsExtension.CalculateAppUsageIntent
com.apple.intelligenceplatform.IntelligencePlatform.IntelligencePlatformDataActionsAppIntentsExtension.FindSportsEvents
com.apple.intelligenceplatformd.PersonalKnowledgeTool
com.apple.journal.AddCurrentLocationEntity
com.apple.journal.AddCurrentLocationEntity-UpdatableEntity
com.apple.journal.AddCurrentLocationIntent
com.apple.journal.AlwaysUseMomentDateEntity
com.apple.journal.AlwaysUseMomentDateEntity-UpdatableEntity
com.apple.journal.AlwaysUseMomentDateIntent
com.apple.journal.CreateEntryAudioIntent
com.apple.journal.CreateEntryIntent
com.apple.journal.OpenEntryEntityIntent
com.apple.journal.OpenJournalSettingsDeeplinks
com.apple.journal.RefreshIntent
com.apple.journal.SaveToPhotosEntity
com.apple.journal.SaveToPhotosEntity-UpdatableEntity
com.apple.journal.SaveToPhotosIntent
com.apple.journal.SearchEntriesIntent
com.apple.journal.SkipJournalingSuggestionsEntity
com.apple.journal.SkipJournalingSuggestionsEntity-UpdatableEntity
com.apple.journal.SkipJournalingSuggestionsIntent
com.apple.journal.StreaksWidgetConfigurationIntent
com.apple.mail.ArchiveMessageIntent
com.apple.mail.BlockSenderIntent
com.apple.mail.CancelDraftIntent
com.apple.mail.ComposeMessageIntent
com.apple.mail.DeleteDraftIntent
com.apple.mail.DeleteMessageIntent
com.apple.mail.DeleteReadLaterIntent
com.apple.mail.ForwardMessageIntent
com.apple.mail.MailFocusConfigurationAction
com.apple.mail.MailMessage
com.apple.mail.MailMessageEntity
com.apple.mail.MuteThreadIntent
com.apple.mail.OpenDraftIntent
com.apple.mail.OpenDraftURLIntent
com.apple.mail.OpenMessageURLIntent
com.apple.mail.RemoveFollowUpIntent
com.apple.mail.ReplyMessageIntent
com.apple.mail.SaveDraftIntent
com.apple.mail.SearchMailIntent
com.apple.mail.SendDraftIntent
com.apple.mail.SendMail
com.apple.mail.SetMailMessageIsRead
com.apple.mail.SetReadLaterIntent
com.apple.mail.SummarizeThreadIntent
com.apple.mail.UndoSendMessageIntent
com.apple.mail.UnsubscribeMessageIntent
com.apple.mail.UpdateDraftIntent
com.apple.mail.UpdateMessageIntent
com.apple.mobilenotes.SharingExtension
com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent
com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent
com.apple.mobiletimer-framework.MobileTimerIntents.MTToggleAlarmIntent
com.apple.news.BlockIntent
com.apple.news.DecreaseTextSizeIntent
com.apple.news.FollowIntent
com.apple.news.GameCenterEntity
com.apple.news.GameCenterEntity-UpdatableEntity
com.apple.news.IncreaseTextSizeIntent
com.apple.news.NewsSettingsAutomaticDownloadDynamicDeepLinks
com.apple.news.NewsSettingsDynamicDeepLinks
com.apple.news.NewsTabDeepLink
com.apple.news.OpenArticleIntent
com.apple.news.OpenFeedIntent
com.apple.news.OpenHistoryIntent
com.apple.news.OpenRecipeIntent
com.apple.news.OpenSavedIntent
com.apple.news.OpenSavedRecipesIntent
com.apple.news.OpenStaticFeed
com.apple.news.RestrictStoriesInTodaySettingEntity
com.apple.news.RestrictStoriesInTodaySettingEntity-UpdatableEntity
com.apple.news.SaveArticleIntent
com.apple.news.ToggleAudioPlaybackIntent
com.apple.news.UnblockIntent
com.apple.news.UnsaveArticleIntent
com.apple.news.WFAppSettingEntityUpdaterAction
com.apple.news.WFGetAppSettingAction
com.apple.omniSearch.SearchToolExtension.OpenFlightReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenGenericEventEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenHotelReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenIDCardBusinessEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenIDCardPersonalEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenMediaEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenRestaurantReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenSearchSpotlightEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenTicketedShowEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenTicketedTransportationEntityIntent
com.apple.omniSearch.SearchToolExtension.OpenVehicleReservationEntityIntent
com.apple.omniSearch.SearchToolExtension.SearchTool
com.apple.omniSearch.SearchToolExtension.SearchToolControl
com.apple.omniSearch.SearchToolExtension.SearchToolMCGrounding
com.apple.omniSearch.SearchToolExtension.SearchToolMCQU
com.apple.podcasts.DownloadEpisodesAppIntent
com.apple.podcasts.FetchShowLatestEpisodesAppIntent
com.apple.podcasts.FollowRSSFeedAppIntent
com.apple.podcasts.FollowShowAppIntent
com.apple.podcasts.MarkEpisodeAsPlayedAppIntent
com.apple.podcasts.MarkEpisodeAsUnplayedAppIntent
com.apple.podcasts.OpenAppLocationAppIntent
com.apple.podcasts.OpenChannelAppIntent
com.apple.podcasts.OpenEpisodeAppIntent
com.apple.podcasts.OpenShowAppIntent
com.apple.podcasts.PlayAudioIntent
com.apple.podcasts.PlayEpisodeAppIntent
com.apple.podcasts.PlayEpisodeLastAppIntent
com.apple.podcasts.PlayEpisodeNextAppIntent
com.apple.podcasts.PlayNextChapterAppIntent
com.apple.podcasts.PlayPauseStationAppIntent
com.apple.podcasts.PlayPauseWidgetIntent
com.apple.podcasts.PlayPreviousChapterAppIntent
com.apple.podcasts.PlayStationAppIntent
com.apple.podcasts.RemoveEpisodesDownloadAppIntent
com.apple.podcasts.SaveEpisodeAppIntent
com.apple.podcasts.SearchPodcastsAppIntent
com.apple.podcasts.SelectLibraryListAppIntent
com.apple.podcasts.SelectWidgetShowAppIntent
com.apple.podcasts.UnfollowShowAppIntent
com.apple.podcasts.UnsaveEpisodeAppIntent
com.apple.podcasts.ViewTranscriptAppIntent
com.apple.printcenter.CancelPrintJob
com.apple.printcenter.LaunchPrintCenterAppIntent
com.apple.printcenter.PrintDocuments
com.apple.reminders.AddOrRemoveTagsAppIntent
com.apple.reminders.CompleteReminderAppIntent
com.apple.reminders.CompleteRemindersAppIntent
com.apple.reminders.CreateCustomSmartListAppIntent
com.apple.reminders.CreateGroupAppIntent
com.apple.reminders.CreateSectionAppIntent
com.apple.reminders.DeleteListsAppIntent
com.apple.reminders.DeleteRemindersAppIntent
com.apple.reminders.DeleteRemindersListGroupsAppIntent
com.apple.reminders.DeleteSectionsAppIntent
com.apple.reminders.GroupEntity-UpdatableEntity
com.apple.reminders.ListEntity-UpdatableEntity
com.apple.reminders.MoveRemindersAppIntent
com.apple.reminders.MoveRemindersToListAppIntent
com.apple.reminders.MoveRemindersToParentReminderAppIntent
com.apple.reminders.MoveRemindersToSectionAppIntent
com.apple.reminders.OpenGroupAppIntent
com.apple.reminders.OpenReminderAppIntent
com.apple.reminders.OpenSectionAppIntent
com.apple.reminders.OpenSmartListAppIntent
com.apple.reminders.OpenTagsAppIntent
com.apple.reminders.RemotePreferencesEntity
com.apple.reminders.SectionEntity-UpdatableEntity
com.apple.reminders.SmartListEntity
com.apple.reminders.TTRCreateListAppIntent
com.apple.reminders.TTRCreateReminderAppIntent
com.apple.reminders.TTROpenListAppIntent
com.apple.reminders.TTROpenSmartListAppIntent
com.apple.reminders.TTRReminderSetCompletedIntent
com.apple.reminders.TTRSearchRemindersAppIntent
com.apple.reminders.UpdateGroupAppIntent
com.apple.reminders.UpdateListAppIntent
com.apple.reminders.UpdateReminderAppIntent
com.apple.reminders.UpdateSectionAppIntent
com.apple.reminders.UpdateSmartListAppIntent
com.apple.reminders.UpdateSmartListIsHiddenAppIntent
com.apple.screenshot.launcher.CaptureScreenIntent
com.apple.screenshot.launcher.CaptureSelectionIntent
com.apple.screenshot.launcher.CustomCaptureConfiguration
com.apple.screenshot.launcher.CustomCaptureIntent
com.apple.screenshot.launcher.CustomRecordConfiguration
com.apple.screenshot.launcher.CustomRecordIntent
com.apple.screenshot.launcher.RecordScreenIntent
com.apple.screenshot.launcher.RecordSelectionIntent
com.apple.shortcuts.AddShortcutToHomeScreenAction
com.apple.shortcuts.ChangeShortcutIconAction
com.apple.shortcuts.CreateFolderAction
com.apple.shortcuts.CreateShortcutiCloudLinkAction
com.apple.shortcuts.CreateWorkflowAction
com.apple.shortcuts.DeleteWorkflowAction
com.apple.shortcuts.GetShortcutAttributesAction
com.apple.shortcuts.MoveShortcutToFolderAction
com.apple.shortcuts.OpenAppIntent
com.apple.shortcuts.OpenNavigationDestinationAction
com.apple.shortcuts.OpenShortcutsStaticDeepLinks
com.apple.shortcuts.OpenWorkflowAction
com.apple.shortcuts.RenameShortcutAction
com.apple.shortcuts.RunShortcutConfigurationIntent
com.apple.shortcuts.RunShortcutFromCollectionIntent
com.apple.shortcuts.RunShortcutIntent
com.apple.shortcuts.SearchActionDrawerAction
com.apple.shortcuts.SearchShortcutsAction
com.apple.shortcuts.SetShortcutAttributesAction
com.apple.shortcuts.ShortcutsFolderConfigurationIntent
com.apple.shortcuts.StopWorkflowAction
com.apple.siri.AssistantSettingsControls.AlwaysPrintSiriResponseEntity
com.apple.siri.AssistantSettingsControls.AlwaysPrintSiriResponseEntity-UpdatableEntity
com.apple.siri.AssistantSettingsControls.AlwaysShowSpeechEntity
com.apple.siri.AssistantSettingsControls.AlwaysShowSpeechEntity-UpdatableEntity
com.apple.siri.AssistantSettingsControls.AskSiriEntity
com.apple.siri.AssistantSettingsControls.KeyboardShortcutEntity
com.apple.siri.AssistantSettingsControls.OpenAlwaysPrintSiriResponseEntity
com.apple.siri.AssistantSettingsControls.OpenAlwaysShowSpeechEntity
com.apple.siri.AssistantSettingsControls.OpenAskSiriEntity
com.apple.siri.AssistantSettingsControls.OpenKeyboardShortcutEntity
com.apple.siri.AssistantSettingsControls.OpenSiriAndDictationHistoryEntity
com.apple.siri.AssistantSettingsControls.OpenSiriLanguageEntity
com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsAndPrivacyEntity
com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsAndPrivacyForAppEntity
com.apple.siri.AssistantSettingsControls.OpenSiriSuggestionsShowInAppEntity
com.apple.siri.AssistantSettingsControls.OpenSiriVoiceEntity
com.apple.siri.AssistantSettingsControls.OpenVoiceFeedbackToggleEntity
com.apple.siri.AssistantSettingsControls.SiriAndDictationHistoryEntity
com.apple.siri.AssistantSettingsControls.SiriLanguageEntity
com.apple.siri.AssistantSettingsControls.SiriSuggestionsAndPrivacyEntity
com.apple.siri.AssistantSettingsControls.SiriSuggestionsAndPrivacyForAppEntity
com.apple.siri.AssistantSettingsControls.SiriSuggestionsAndPrivacyForAppEntity-UpdatableEntity
com.apple.siri.AssistantSettingsControls.SiriSuggestionsShowInAppEntity
com.apple.siri.AssistantSettingsControls.SiriSuggestionsShowInAppEntity-UpdatableEntity
com.apple.siri.AssistantSettingsControls.SiriVoiceEntity
com.apple.siri.AssistantSettingsControls.VoiceFeedbackToggleEntity
com.apple.siri.AssistantSettingsControls.VoiceFeedbackToggleEntity-UpdatableEntity
com.apple.stocks.AddSymbolToWatchlistIntent
com.apple.stocks.BlockIntent
com.apple.stocks.DecreaseTextSizeIntent
com.apple.stocks.DeleteSymbolFromWatchlistIntent
com.apple.stocks.DeleteWatchlistsIntent
com.apple.stocks.FollowIntent
com.apple.stocks.GetSymbolQuoteIntent
com.apple.stocks.IncreaseTextSizeIntent
com.apple.stocks.NewWatchlistIntent
com.apple.stocks.NewsTabDeepLink
com.apple.stocks.OpenArticleIntent
com.apple.stocks.OpenBusinessNewsIntent
com.apple.stocks.OpenFeedIntent
com.apple.stocks.OpenHistoryIntent
com.apple.stocks.OpenRecipeIntent
com.apple.stocks.OpenSavedIntent
com.apple.stocks.OpenSavedRecipesIntent
com.apple.stocks.OpenStaticFeed
com.apple.stocks.OpenSymbolIntent
com.apple.stocks.OpenWatchlistIntent
com.apple.stocks.SaveArticleIntent
com.apple.stocks.StockIntent
com.apple.stocks.StocksOverviewIntent
com.apple.stocks.SymbolEntity
com.apple.stocks.SymbolWidgetEntity
com.apple.stocks.UnblockIntent
com.apple.stocks.UnsaveArticleIntent
com.apple.stocks.WatchlistEntity
com.apple.shortcuts.OpenShortcutsStaticDeepLinks
com.apple.wallpaper.agent.SetWallpaperIntent
com.apple.wallpaper.agent.SetWallpaperPhotoIntent
com.apple.wallpaper.agent.SkipShuffledContentAction
com.apple.wallpaper.agent.WallpaperEntity
com.apple.weather.AddSavedLocationIntent
com.apple.weather.LocationEntity
com.apple.weather.LocationSearchEntity
com.apple.weather.OpenMoonIntent
com.apple.weather.OpenNotificationsConfigurationIntent
com.apple.weather.OpenSunriseSunsetIntent
com.apple.weather.OpenUnitsConfigurationIntent
com.apple.weather.OpenWeatherAirQualityIntent
com.apple.weather.OpenWeatherSpecificConditionIntent
com.apple.weather.PreferredUnitsEntity
com.apple.weather.RemoveSavedLocationIntent
com.apple.weather.ResetUnitsIntent
com.apple.weather.SetDistanceUnitIntent
com.apple.weather.SetPrecipitationUnitIntent
com.apple.weather.SetPressureUnitIntent
com.apple.weather.SetTemperatureUnitIntent
com.apple.weather.SetWindUnitIntent
```

> **Note:** `is.workflow.actions.appendnote`, `is.workflow.actions.filter.notes`, and `is.workflow.actions.shownote` are WF-namespace actions documented in [ACTIONS.md](ACTIONS.md), not AppIntents.

---

## Invocation Template

To invoke any AppIntent:
```
<dict>
    <key>WFWorkflowActionIdentifier</key>
    <string>APP_INTENT_FULL_ID</string>
    <key>WFWorkflowActionParameters</key>
    <dict>
        <key>AppIntentDescriptor</key>
        <dict>
            <key>BundleIdentifier</key>
            <string>APP_BUNDLE_ID</string>
            <key>Name</key>
            <string>DISPLAY_NAME</string>
            <key>AppIntentIdentifier</key>
            <string>APP_INTENT_IDENTIFIER</string>
        </dict>
        <!-- Additional parameters as needed -->
    </dict>
</dict>
```

Common Bundle Identifiers:
- `com.apple.Safari` - Safari
- `com.apple.Notes` - Notes
- `com.apple.reminders` - Reminders
- `com.apple.iCal` - Calendar
- `com.apple.clock` - Clock
