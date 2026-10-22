// FeedItem.m
#import "FeedItem.h"

static UIColor *C(CGFloat r, CGFloat g, CGFloat b) { return [UIColor colorWithRed:r/255 green:g/255 blue:b/255 alpha:1]; }

@implementation FeedItem

+ (NSArray<FeedItem *> *)sampleItems {
    struct { const char *a, *c, *m; CGFloat r1,g1,b1,r2,g2,b2; NSInteger l, cm; } d[] = {
        {"@pika_lab",   "Portrait paging hand-written in ObjC, no Xcode #iOSDev",  "Original Sound - pika_lab",  255, 94, 98,  255,195,113, 12800, 342},
        {"@clang_daily","clang + lld compiling on the phone, a build in 3 seconds", "Compile Beat - clang",       67,206,162,   24, 90,157, 45300, 1201},
        {"@rcodesign",  "No computer: sign and install the whole way from an Apple ID ✍️", "Sign It - rcodesign", 142, 45,226,   74,  0,224,  9876, 210},
        {"@surge_loop", "10.7.0.1 loopback: plugging the cable back into itself",   "Loopback - surge",            0,198,255,    0,114,255, 30100, 678},
        {"@minis_dev",  "Re-signed every 7 days, fully scripted",                   "Cron Jam - minis",          252, 74, 26,  247,183, 51,  7421, 96},
        {"@ish_guest",  "Alpine running inside an iPhone, musl builds Rust too",    "Static Link - ish",          17, 153,142,   56,239,125, 51200, 2310},
    };
    NSMutableArray *out = [NSMutableArray array];
    for (size_t i = 0; i < sizeof(d)/sizeof(d[0]); i++) {
        FeedItem *it = [FeedItem new];
        it.author = [NSString stringWithUTF8String:d[i].a];
        it.caption = [NSString stringWithUTF8String:d[i].c];
        it.music = [NSString stringWithUTF8String:d[i].m];
        it.colorA = C(d[i].r1, d[i].g1, d[i].b1);
        it.colorB = C(d[i].r2, d[i].g2, d[i].b2);
        it.likes = d[i].l; it.comments = d[i].cm;
        [out addObject:it];
    }
    return out;
}

@end
