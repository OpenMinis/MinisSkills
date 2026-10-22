// FeedItem.h — Mock "video" data. There is no real video source, so it uses a gradient plus placeholder copy, and the UI says so honestly.
#import <UIKit/UIKit.h>

@interface FeedItem : NSObject
@property (nonatomic, copy) NSString *author;
@property (nonatomic, copy) NSString *caption;
@property (nonatomic, copy) NSString *music;
@property (nonatomic, strong) UIColor *colorA;
@property (nonatomic, strong) UIColor *colorB;
@property (nonatomic, assign) NSInteger likes;
@property (nonatomic, assign) NSInteger comments;
@property (nonatomic, assign) BOOL liked;
+ (NSArray<FeedItem *> *)sampleItems;
@end
