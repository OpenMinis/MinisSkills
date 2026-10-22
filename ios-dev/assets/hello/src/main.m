#import <UIKit/UIKit.h>
#include "util.h"

@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property (nonatomic, strong) UIWindow *window;
@end

@implementation AppDelegate

- (BOOL)application:(UIApplication *)app didFinishLaunchingWithOptions:(NSDictionary *)opts {
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];

    UIViewController *vc = [UIViewController new];
    vc.view.backgroundColor = UIColor.systemYellowColor;

    UILabel *title = [UILabel new];
    title.text = @"Hello World ⚡";
    title.font = [UIFont boldSystemFontOfSize:36];
    title.textAlignment = NSTextAlignmentCenter;
    title.translatesAutoresizingMaskIntoConstraints = NO;

    UILabel *sub = [UILabel new];
    // Call a C function to verify the ObjC + C mixed build
    sub.text = [NSString stringWithFormat:@"Built on iPhone, no Xcode\n2 + 3 = %d", add_ints(2, 3)];
    sub.numberOfLines = 0;
    sub.font = [UIFont systemFontOfSize:17];
    sub.textColor = UIColor.darkGrayColor;
    sub.textAlignment = NSTextAlignmentCenter;
    sub.translatesAutoresizingMaskIntoConstraints = NO;

    [vc.view addSubview:title];
    [vc.view addSubview:sub];
    [NSLayoutConstraint activateConstraints:@[
        [title.centerXAnchor constraintEqualToAnchor:vc.view.centerXAnchor],
        [title.centerYAnchor constraintEqualToAnchor:vc.view.centerYAnchor constant:-20],
        [sub.centerXAnchor constraintEqualToAnchor:vc.view.centerXAnchor],
        [sub.topAnchor constraintEqualToAnchor:title.bottomAnchor constant:16],
    ]];

    self.window.rootViewController = vc;
    [self.window makeKeyAndVisible];
    return YES;
}

@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([AppDelegate class]));
    }
}
