// main.m — Swipe Demo: imitates the portrait paging interaction of a short-video app (pure UIKit, no real video source).
#import <UIKit/UIKit.h>
#import "FeedItem.h"
#import "FeedPageView.h"

@interface FeedVC : UIViewController <UIScrollViewDelegate>
@property (nonatomic, strong) UIScrollView *scroll;
@property (nonatomic, strong) NSArray<FeedItem *> *items;
@property (nonatomic, strong) NSMutableDictionary<NSNumber *, FeedPageView *> *pages;
@property (nonatomic, assign) NSInteger current;
@property (nonatomic, strong) UIView *tabBar;
@property (nonatomic, assign) CGFloat pageH;
@end

@implementation FeedVC

- (BOOL)prefersStatusBarHidden { return YES; }

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = UIColor.blackColor;
    _items = [FeedItem sampleItems];
    _pages = [NSMutableDictionary dictionary];
    _current = -1;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    if (_scroll) return;
    CGRect b = self.view.bounds;
    CGFloat tabH = 56 + self.view.safeAreaInsets.bottom;
    _pageH = b.size.height - tabH;

    _scroll = [[UIScrollView alloc] initWithFrame:CGRectMake(0, 0, b.size.width, _pageH)];
    _scroll.pagingEnabled = YES;
    _scroll.showsVerticalScrollIndicator = NO;
    _scroll.contentSize = CGSizeMake(b.size.width, _pageH * _items.count);
    _scroll.delegate = self;
    _scroll.bounces = YES;
    if (@available(iOS 11.0, *)) _scroll.contentInsetAdjustmentBehavior = UIScrollViewContentInsetAdjustmentNever;
    [self.view addSubview:_scroll];

    [self buildTopBar:b];
    [self buildTabBar:b tabH:tabH];
    [self showPage:0];
}

- (void)buildTopBar:(CGRect)b {
    UIView *top = [[UIView alloc] initWithFrame:CGRectMake(0, self.view.safeAreaInsets.top, b.size.width, 40)];
    NSArray *titles = @[@"Following", @"For You"];
    CGFloat x = b.size.width / 2 - 70;
    for (NSString *t in titles) {
        UILabel *l = [[UILabel alloc] initWithFrame:CGRectMake(x, 6, 70, 28)];
        l.text = t; l.textAlignment = NSTextAlignmentCenter;
        BOOL sel = [t isEqualToString:@"For You"];
        l.font = [UIFont systemFontOfSize:17 weight:sel ? UIFontWeightBold : UIFontWeightRegular];
        l.textColor = [UIColor colorWithWhite:1 alpha:sel ? 1 : 0.6];
        [top addSubview:l];
        if (sel) {
            UIView *u = [[UIView alloc] initWithFrame:CGRectMake(x + 22, 34, 26, 3)];
            u.backgroundColor = UIColor.whiteColor; u.layer.cornerRadius = 1.5; [top addSubview:u];
        }
        x += 70;
    }
    [self.view addSubview:top];
}

- (void)buildTabBar:(CGRect)b tabH:(CGFloat)tabH {
    _tabBar = [[UIView alloc] initWithFrame:CGRectMake(0, b.size.height - tabH, b.size.width, tabH)];
    _tabBar.backgroundColor = UIColor.blackColor;
    NSArray *tabs = @[@"Home", @"Friends", @"+", @"Messages", @"Me"];
    CGFloat w = b.size.width / tabs.count;
    for (NSUInteger i = 0; i < tabs.count; i++) {
        UILabel *l = [[UILabel alloc] initWithFrame:CGRectMake(w * i, 0, w, 56)];
        l.text = tabs[i]; l.textAlignment = NSTextAlignmentCenter;
        if (i == 2) {
            l.font = [UIFont boldSystemFontOfSize:22]; l.textColor = UIColor.blackColor;
            l.backgroundColor = UIColor.whiteColor; l.layer.cornerRadius = 8; l.layer.masksToBounds = YES;
            l.frame = CGRectMake(w * i + w/2 - 24, 12, 48, 32);
        } else {
            l.font = [UIFont systemFontOfSize:16 weight:i == 0 ? UIFontWeightBold : UIFontWeightRegular];
            l.textColor = [UIColor colorWithWhite:1 alpha:i == 0 ? 1 : 0.6];
        }
        [_tabBar addSubview:l];
    }
    [self.view addSubview:_tabBar];
}

#pragma mark - Page management (keep only 1 page before and after the current page)

- (FeedPageView *)pageAt:(NSInteger)i {
    if (i < 0 || i >= (NSInteger)_items.count) return nil;
    FeedPageView *p = _pages[@(i)];
    if (!p) {
        p = [[FeedPageView alloc] initWithFrame:CGRectMake(0, _pageH * i, _scroll.bounds.size.width, _pageH) item:_items[i]];
        [_scroll addSubview:p]; _pages[@(i)] = p;
    }
    return p;
}

- (void)showPage:(NSInteger)idx {
    if (idx == _current) return;
    NSInteger old = _current; _current = idx;
    for (NSInteger k = idx - 1; k <= idx + 1; k++) [self pageAt:k];
    for (NSNumber *key in [_pages.allKeys copy]) {          // Recycle distant pages to keep memory bounded
        if (labs(key.integerValue - idx) > 1) { [_pages[key] removeFromSuperview]; [_pages removeObjectForKey:key]; }
    }
    if (old >= 0) [_pages[@(old)] setActive:NO];
    [_pages[@(idx)] setActive:YES];
}

- (void)scrollViewDidScroll:(UIScrollView *)s {
    NSInteger idx = (NSInteger)llround(s.contentOffset.y / _pageH);
    idx = MAX(0, MIN(idx, (NSInteger)_items.count - 1));
    if (idx != _current) { [self showPage:idx]; [UISelectionFeedbackGenerator.new selectionChanged]; }
}

@end

@interface AD : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end
@implementation AD
- (BOOL)application:(UIApplication *)a didFinishLaunchingWithOptions:(NSDictionary *)o {
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = [FeedVC new];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass([AD class])); }
}
