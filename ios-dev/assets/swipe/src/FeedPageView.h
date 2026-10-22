// FeedPageView.h — one screen of "video".
#import <UIKit/UIKit.h>
#import "FeedItem.h"

@interface FeedPageView : UIView
@property (nonatomic, strong, readonly) FeedItem *item;
- (instancetype)initWithFrame:(CGRect)frame item:(FeedItem *)item;
- (void)setActive:(BOOL)active;     // Start/stop animations and the progress bar when entering/leaving the screen
- (void)toggleLike;                  // Like button
@end
