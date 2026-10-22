// FeedPageView.m
#import "FeedPageView.h"
#import <QuartzCore/QuartzCore.h>

static NSString *Fmt(NSInteger n) {
    if (n >= 10000) return [NSString stringWithFormat:@"%.1fw", n / 10000.0];
    return [NSString stringWithFormat:@"%ld", (long)n];
}

@interface FeedPageView ()
@property (nonatomic, strong) FeedItem *item;
@property (nonatomic, strong) CAGradientLayer *bg;
@property (nonatomic, strong) UIView *orbA, *orbB;
@property (nonatomic, strong) UIView *progressTrack, *progressFill;
@property (nonatomic, strong) UIButton *likeBtn;
@property (nonatomic, strong) UILabel *likeLabel, *commentLabel, *pausedIcon;
@property (nonatomic, strong) UIView *disc;
@property (nonatomic, assign) BOOL paused;
@end

@implementation FeedPageView

- (instancetype)initWithFrame:(CGRect)f item:(FeedItem *)item {
    if ((self = [super initWithFrame:f])) {
        _item = item;
        self.clipsToBounds = YES;
        [self buildBackground];
        [self buildSideBar];
        [self buildCaption];
        [self buildProgress];
        [self buildGestures];
    }
    return self;
}

#pragma mark - Construction

- (void)buildBackground {
    _bg = [CAGradientLayer layer];
    _bg.frame = self.bounds;
    _bg.colors = @[(id)_item.colorA.CGColor, (id)_item.colorB.CGColor];
    _bg.startPoint = CGPointMake(0, 0); _bg.endPoint = CGPointMake(1, 1);
    [self.layer addSublayer:_bg];

    CGFloat w = self.bounds.size.width;
    _orbA = [[UIView alloc] initWithFrame:CGRectMake(-w*0.2, self.bounds.size.height*0.15, w*0.8, w*0.8)];
    _orbB = [[UIView alloc] initWithFrame:CGRectMake(w*0.4, self.bounds.size.height*0.45, w*0.7, w*0.7)];
    for (UIView *o in @[_orbA, _orbB]) {
        o.backgroundColor = [UIColor colorWithWhite:1 alpha:0.12];
        o.layer.cornerRadius = o.bounds.size.width / 2;
        [self addSubview:o];
    }

    UILabel *tag = [[UILabel alloc] initWithFrame:CGRectMake(0, 70, w, 20)];
    tag.text = @"Simulated video · no real video source";
    tag.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    tag.textColor = [UIColor colorWithWhite:1 alpha:0.55];
    tag.textAlignment = NSTextAlignmentCenter;
    [self addSubview:tag];

    _pausedIcon = [[UILabel alloc] initWithFrame:self.bounds];
    _pausedIcon.text = @"▶︎";
    _pausedIcon.font = [UIFont systemFontOfSize:84];
    _pausedIcon.textColor = [UIColor colorWithWhite:1 alpha:0.75];
    _pausedIcon.textAlignment = NSTextAlignmentCenter;
    _pausedIcon.alpha = 0;
    [self addSubview:_pausedIcon];
}

- (UIButton *)iconButton:(NSString *)emoji y:(CGFloat)y action:(SEL)sel {
    UIButton *b = [UIButton buttonWithType:UIButtonTypeCustom];
    b.frame = CGRectMake(self.bounds.size.width - 64, y, 52, 52);
    [b setTitle:emoji forState:UIControlStateNormal];
    b.titleLabel.font = [UIFont systemFontOfSize:34];
    [b addTarget:self action:sel forControlEvents:UIControlEventTouchUpInside];
    b.layer.shadowColor = UIColor.blackColor.CGColor; b.layer.shadowOpacity = 0.35;
    b.layer.shadowRadius = 4; b.layer.shadowOffset = CGSizeMake(0, 2);
    [self addSubview:b];
    return b;
}

- (UILabel *)countLabelBelow:(UIView *)v text:(NSString *)t {
    UILabel *l = [[UILabel alloc] initWithFrame:CGRectMake(v.frame.origin.x - 6, CGRectGetMaxY(v.frame), 64, 18)];
    l.text = t; l.textAlignment = NSTextAlignmentCenter;
    l.font = [UIFont systemFontOfSize:12 weight:UIFontWeightSemibold]; l.textColor = UIColor.whiteColor;
    [self addSubview:l];
    return l;
}

- (void)buildSideBar {
    CGFloat h = self.bounds.size.height;
    CGFloat base = h * 0.46;

    UILabel *avatar = [[UILabel alloc] initWithFrame:CGRectMake(self.bounds.size.width - 62, base - 70, 48, 48)];
    avatar.text = [_item.author substringWithRange:NSMakeRange(1, 1)].uppercaseString;
    avatar.textAlignment = NSTextAlignmentCenter;
    avatar.font = [UIFont boldSystemFontOfSize:22]; avatar.textColor = UIColor.whiteColor;
    avatar.backgroundColor = [UIColor colorWithWhite:0 alpha:0.35];
    avatar.layer.cornerRadius = 24; avatar.layer.masksToBounds = YES;
    avatar.layer.borderWidth = 2; avatar.layer.borderColor = UIColor.whiteColor.CGColor;
    [self addSubview:avatar];

    _likeBtn = [self iconButton:(_item.liked ? @"❤️" : @"🤍") y:base action:@selector(toggleLike)];
    _likeLabel = [self countLabelBelow:_likeBtn text:Fmt(_item.likes)];
    UIButton *cm = [self iconButton:@"💬" y:base + 82 action:@selector(commentTap)];
    _commentLabel = [self countLabelBelow:cm text:Fmt(_item.comments)];
    UIButton *sh = [self iconButton:@"↗️" y:base + 164 action:@selector(shareTap)];
    [self countLabelBelow:sh text:@"Share"];

    _disc = [[UIView alloc] initWithFrame:CGRectMake(self.bounds.size.width - 62, h - 190, 46, 46)];
    _disc.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.9];
    _disc.layer.cornerRadius = 23; _disc.layer.borderWidth = 8; _disc.layer.borderColor = [UIColor colorWithWhite:0.15 alpha:1].CGColor;
    UILabel *note = [[UILabel alloc] initWithFrame:_disc.bounds];
    note.text = @"♪"; note.textAlignment = NSTextAlignmentCenter; note.textColor = UIColor.whiteColor;
    [_disc addSubview:note];
    [self addSubview:_disc];
}

- (void)buildCaption {
    CGFloat h = self.bounds.size.height, w = self.bounds.size.width;
    UILabel *au = [[UILabel alloc] initWithFrame:CGRectMake(16, h - 190, w - 100, 24)];
    au.text = _item.author; au.font = [UIFont boldSystemFontOfSize:18]; au.textColor = UIColor.whiteColor;
    [self addSubview:au];

    UILabel *cap = [[UILabel alloc] initWithFrame:CGRectMake(16, h - 160, w - 100, 52)];
    cap.text = _item.caption; cap.numberOfLines = 2;
    cap.font = [UIFont systemFontOfSize:15]; cap.textColor = [UIColor colorWithWhite:1 alpha:0.95];
    [self addSubview:cap];

    UILabel *mu = [[UILabel alloc] initWithFrame:CGRectMake(16, h - 100, w - 100, 20)];
    mu.text = [@"♫ " stringByAppendingString:_item.music];
    mu.font = [UIFont systemFontOfSize:13]; mu.textColor = [UIColor colorWithWhite:1 alpha:0.85];
    [self addSubview:mu];
}

- (void)buildProgress {
    CGFloat h = self.bounds.size.height, w = self.bounds.size.width;
    _progressTrack = [[UIView alloc] initWithFrame:CGRectMake(0, h - 3, w, 3)];
    _progressTrack.backgroundColor = [UIColor colorWithWhite:1 alpha:0.25];
    _progressFill = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 0, 3)];
    _progressFill.backgroundColor = UIColor.whiteColor;
    [_progressTrack addSubview:_progressFill];
    [self addSubview:_progressTrack];
}

- (void)buildGestures {
    UITapGestureRecognizer *dbl = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(doubleTap:)];
    dbl.numberOfTapsRequired = 2;
    UITapGestureRecognizer *one = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(singleTap)];
    [one requireGestureRecognizerToFail:dbl];
    [self addGestureRecognizer:dbl]; [self addGestureRecognizer:one];
}

#pragma mark - Interaction

- (void)singleTap {
    _paused = !_paused;
    [UIView animateWithDuration:0.15 animations:^{ self.pausedIcon.alpha = self.paused ? 1 : 0; }];
    [self applyPause];
}

- (void)doubleTap:(UITapGestureRecognizer *)g {
    if (!_item.liked) [self toggleLike];
    [self flyHeartAt:[g locationInView:self]];
}

- (void)toggleLike {
    _item.liked = !_item.liked;
    _item.likes += _item.liked ? 1 : -1;
    [_likeBtn setTitle:(_item.liked ? @"❤️" : @"🤍") forState:UIControlStateNormal];
    _likeLabel.text = Fmt(_item.likes);
    [UIImpactFeedbackGenerator.new impactOccurred];
    _likeBtn.transform = CGAffineTransformMakeScale(0.6, 0.6);
    [UIView animateWithDuration:0.45 delay:0 usingSpringWithDamping:0.35 initialSpringVelocity:8
                        options:0 animations:^{ self.likeBtn.transform = CGAffineTransformIdentity; } completion:nil];
}

- (void)commentTap { [self toast:@"Comments (not implemented in this demo)"]; }
- (void)shareTap   { [self toast:@"Share (not implemented in this demo)"]; }

- (void)toast:(NSString *)s {
    UILabel *t = [[UILabel alloc] init];
    t.text = [NSString stringWithFormat:@"  %@  ", s]; t.font = [UIFont systemFontOfSize:14]; t.textColor = UIColor.whiteColor;
    t.backgroundColor = [UIColor colorWithWhite:0 alpha:0.7]; t.layer.cornerRadius = 14; t.layer.masksToBounds = YES;
    [t sizeToFit]; t.frame = CGRectMake(0, 0, t.frame.size.width, 32);
    t.center = CGPointMake(self.bounds.size.width / 2, self.bounds.size.height * 0.2);
    t.alpha = 0; [self addSubview:t];
    [UIView animateWithDuration:0.2 animations:^{ t.alpha = 1; } completion:^(BOOL f){
        [UIView animateWithDuration:0.3 delay:1.0 options:0 animations:^{ t.alpha = 0; } completion:^(BOOL f2){ [t removeFromSuperview]; }];
    }];
}

- (void)flyHeartAt:(CGPoint)p {
    UILabel *h = [[UILabel alloc] initWithFrame:CGRectMake(0, 0, 100, 100)];
    h.text = @"❤️"; h.font = [UIFont systemFontOfSize:80]; h.textAlignment = NSTextAlignmentCenter; h.center = p;
    CGFloat tilt = ((arc4random() % 40) - 20) * M_PI / 180.0;
    h.transform = CGAffineTransformRotate(CGAffineTransformMakeScale(0.3, 0.3), tilt);
    [self addSubview:h];
    [UIView animateWithDuration:0.25 delay:0 usingSpringWithDamping:0.5 initialSpringVelocity:10 options:0 animations:^{
        h.transform = CGAffineTransformRotate(CGAffineTransformMakeScale(1.1, 1.1), tilt);
    } completion:^(BOOL f){
        [UIView animateWithDuration:0.5 delay:0.15 options:UIViewAnimationOptionCurveEaseIn animations:^{
            h.alpha = 0; h.center = CGPointMake(p.x, p.y - 120);
            h.transform = CGAffineTransformRotate(CGAffineTransformMakeScale(1.6, 1.6), tilt);
        } completion:^(BOOL f2){ [h removeFromSuperview]; }];
    }];
}

#pragma mark - Animation start/stop

- (void)setActive:(BOOL)active {
    if (active) {
        _paused = NO; _pausedIcon.alpha = 0;
        [self startAnimations];
    } else {
        [self stopAnimations];
    }
}

- (void)startAnimations {
    [self stopAnimations];
    for (UIView *o in @[_orbA, _orbB]) {
        BOOL a = (o == _orbA);
        CABasicAnimation *x = [CABasicAnimation animationWithKeyPath:@"transform.translation.x"];
        x.fromValue = @(a ? -30 : 30); x.toValue = @(a ? 40 : -40);
        x.duration = a ? 5 : 7; x.autoreverses = YES; x.repeatCount = HUGE_VALF;
        x.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
        [o.layer addAnimation:x forKey:@"drift"];
        CABasicAnimation *s = [CABasicAnimation animationWithKeyPath:@"transform.scale"];
        s.fromValue = @1.0; s.toValue = @1.25; s.duration = a ? 3.5 : 4.5; s.autoreverses = YES; s.repeatCount = HUGE_VALF;
        [o.layer addAnimation:s forKey:@"pulse"];
    }
    CABasicAnimation *spin = [CABasicAnimation animationWithKeyPath:@"transform.rotation.z"];
    spin.toValue = @(M_PI * 2); spin.duration = 4; spin.repeatCount = HUGE_VALF;
    [_disc.layer addAnimation:spin forKey:@"spin"];

    _progressFill.frame = CGRectMake(0, 0, 0, 3);
    [UIView animateWithDuration:12 delay:0 options:UIViewAnimationOptionCurveLinear animations:^{
        self.progressFill.frame = CGRectMake(0, 0, self.bounds.size.width, 3);
    } completion:nil];
}

- (void)stopAnimations {
    [_orbA.layer removeAllAnimations]; [_orbB.layer removeAllAnimations]; [_disc.layer removeAllAnimations];
    [_progressFill.layer removeAllAnimations];
}

- (void)applyPause {
    CALayer *layers[] = { _orbA.layer, _orbB.layer, _disc.layer, _progressFill.layer };
    for (int i = 0; i < 4; i++) {
        CALayer *l = layers[i];
        if (_paused) {
            CFTimeInterval t = [l convertTime:CACurrentMediaTime() fromLayer:nil];
            l.speed = 0; l.timeOffset = t;
        } else {
            CFTimeInterval t = l.timeOffset; l.speed = 1; l.timeOffset = 0; l.beginTime = 0;
            l.beginTime = [l convertTime:CACurrentMediaTime() fromLayer:nil] - t;
        }
    }
}

@end
