"""Native 800x480 Pearl White Pro radio dashboard for official Pi touchscreen.
Pygame only; audio playback remains owned by touch_radio.py.
"""
import pygame
import os
from ios_ipod_ui import raised_card, THEMES
from fa_icons import draw_icon

BG=(0,0,0); INK=(245,245,245); MUTED=(166,166,166)
BLUE=(96,165,250); NAVY=(23,23,23); WHITE=(240,240,240)
GOLD=(230,230,230)
SKY=(10,39,79)
def scenic_background(s):
    """True black background for the 800x480 official touchscreen."""
    s.fill((0,0,0))

def _glow_card(s,rect,fill=(14,14,14),edge=(60,60,60),radius=18):
    """Minimal flat dark card: no glow, shadow or bright bevel."""
    pygame.draw.rect(s,fill,rect,border_radius=radius)
    pygame.draw.rect(s,edge,rect,1,border_radius=radius)
    pygame.draw.line(s,(min(255,edge[0]+35),)*3,(rect.x+radius,rect.y+1),(rect.right-radius,rect.y+1),1)

SIDEBAR=pygame.Rect(0,55,145,425)
NAV=("HOME","RADIO","BIBLE","YOUTUBE","FAVORITES","CLOCK","WEATHER","SETTINGS")
NAV_ICONS=("home","radio","bible","youtube","favorites","clock","weather","settings")
CARDS=("RADIO","BIBLE","YOUTUBE","FAVORITES")
CARD_ICONS=("radio","bible","youtube","favorites")
NAV_RECTS={n:pygame.Rect(8,65+i*43,130,39) for i,n in enumerate(NAV)}
CARD_RECTS={n:pygame.Rect(158+i*158,346,150,43) for i,n in enumerate(CARDS)}
PREV=pygame.Rect(588,226,49,48)
PAUSE=pygame.Rect(652,226,49,48)
NEXT=pygame.Rect(716,226,49,48)
VOLUME=pygame.Rect(421,268,240,20)
MINI=pygame.Rect(157,399,629,65)
MINI_PREV=pygame.Rect(634,410,43,44)
MINI_PAUSE=pygame.Rect(683,406,50,51)
MINI_NEXT=pygame.Rect(737,410,43,44)
ARTWORK=pygame.Rect(165,83,183,183)
MAIN=pygame.Rect(155,72,635,208)
MINI_OPEN=pygame.Rect(157,399,465,65)
LOGO_CACHE={}

def _station_art(s,rect,station_data,loaded_logo=None):
    """Use a supplied local station logo; fall back to a radio symbol."""
    path=next((station_data.get(k) for k in ("logo","logo_path","image","icon") if isinstance(station_data.get(k),str) and os.path.isfile(station_data.get(k))),None) if isinstance(station_data,dict) else None
    if path:
        try:
            if path not in LOGO_CACHE:
                LOGO_CACHE[path]=pygame.image.load(path).convert_alpha()
            original=LOGO_CACHE[path]
            scale=min((rect.width-12)/original.get_width(),(rect.height-12)/original.get_height())
            image=pygame.transform.smoothscale(original,(max(1,round(original.get_width()*scale)),max(1,round(original.get_height()*scale))))
            s.blit(image,image.get_rect(center=rect.center))
            return
        except (pygame.error,OSError,ValueError):pass
    # The main player already downloads remote artwork from station logo URLs.
    # Reuse that surface rather than requiring a local filesystem path.
    if loaded_logo is not None:
        try:
            original = loaded_logo
            scale = min((rect.width-12)/original.get_width(), (rect.height-12)/original.get_height())
            image = pygame.transform.smoothscale(original, (max(1,round(original.get_width()*scale)), max(1,round(original.get_height()*scale))))
            s.blit(image, image.get_rect(center=rect.center))
            return
        except (pygame.error, ValueError, AttributeError):
            pass
    _icon(s,"radio",rect,min(rect.width,rect.height)//2,WHITE)


def _text(s,font,value,pos,color=INK,max_width=None):
    value=str(value or "")
    if max_width:
        original=value
        # UnicodeFont adapters may expose .size as an integer; rendered
        # surfaces provide a consistent pixel width across font backends.
        while value and font.render(value, True, color).get_width()>max_width:
            value=value[:-1]
        if value and value!=original:
            while value and font.render(value+"…", True, color).get_width()>max_width:
                value=value[:-1]
            value=value.rstrip()+"…"
    s.blit(font.render(value,True,color),pos)

def _icon(s,name,rect,size=24,color=BLUE):
    try:draw_icon(s,name,rect.center,size,color)
    except Exception:pass

def _card(s,rect,radius=17):
    
    pygame.draw.rect(s,(19,19,19),rect,border_radius=radius)
    pygame.draw.rect(s,(59,59,59),rect,1,border_radius=radius)
    pygame.draw.line(s,(85,85,85),(rect.x+radius,rect.y+1),(rect.right-radius,rect.y+1),1)


def _video_clock(value):
    """Readable duration for the currently playing mpv source."""
    try:
        seconds = max(0, int(float(value or 0)))
    except (ValueError, TypeError, OverflowError):
        seconds = 0
    hours, minute_seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(minute_seconds, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


VIDEO_HERO_SEEK = pygame.Rect(421, 294, 329, 8)
VIDEO_HERO_ART = pygame.Rect(163, 79, 225, 265)


def video_hero_hit(pos, status, active_page):
    """Video-only hero hit targets; avoid VLC volume-slider overlap."""
    if active_page != "radio" or not status or not status.get("playing"):
        return None
    if VIDEO_HERO_SEEK.inflate(0, 20).collidepoint(pos):
        duration = float(status.get("duration") or 0)
        if duration > 0:
            ratio = max(0, min(1, (pos[0] - VIDEO_HERO_SEEK.x) / VIDEO_HERO_SEEK.width))
            return ("seek", duration * ratio)
        return ("consume", None)
    if VIDEO_HERO_ART.collidepoint(pos):
        return ("restore", None)
    return None


def _media_source(status):
    source = (status or {}).get("source") or "youtube_video"
    return {
        "youtube_video": ("YOUTUBE", "youtube", "VIDEO PLAYER"),
        "guest_video": ("GUEST VIDEO", "film", "PI RADIO CAST"),
        "guest_audio": ("GUEST AUDIO", "music", "PI RADIO CAST"),
        "guest_photos": ("PHOTOS", "image", "SLIDESHOW"),
        "screen_mirror": ("SCREEN MIRROR", "monitor", "ANDROID SCREEN"),
    }.get(source, ("MEDIA", "radio", "PI RADIO CAST"))


def draw_video_hero(s, font, small, tiny, status):
    """Replace the stale VLC radio hero with the real mpv video session."""
    art = pygame.Rect(163, 79, 225, 265)
    main = pygame.Rect(399, 79, 384, 265)
    _glow_card(s, art, (13, 13, 13), (65, 65, 65), 20)
    _glow_card(s, main, (13, 13, 13), (65, 65, 65), 20)

    # Show the current guest media type, not the previous station's artwork.
    source_label, source_icon, source_hint = _media_source(status)
    artwork = pygame.Rect(193, 115, 165, 155)
    pygame.draw.rect(s, (25, 25, 25), artwork, border_radius=18)
    pygame.draw.rect(s, (56, 56, 56), artwork, 1, border_radius=18)
    pygame.draw.circle(s, (239, 239, 239), artwork.center, 49)
    _icon(s, source_icon, artwork, 53, (20, 20, 20))
    _text(s, small, source_label, (214, 285), WHITE, 166)
    _text(s, tiny, source_hint, (211, 313), MUTED, 166)

    minimized = bool(status.get("minimized"))
    paused = bool(status.get("paused"))
    _text(s, tiny, source_label + "  /  " + ("AUDIO ONLY" if minimized else "PLAYING"),
          (420, 101), (220, 220, 220), 340)
    _text(s, font, status.get("title") or "YouTube video",
          (420, 143), WHITE, 340)
    _text(s, small, "Paused" if paused else
          ("Playing in background" if minimized else source_hint.title()),
          (421, 183), MUTED, 310)

    # Main transport controls target mpv's existing IPC socket.
    for rect, icon in ((PREV, "prev"), (PAUSE, "play" if paused else "pause"),
                       (NEXT, "next")):
        _icon(s, icon, rect, 29, WHITE)
    _text(s, tiny, "-10s", (587, 267), MUTED, 47)
    _text(s, tiny, "+10s", (718, 267), MUTED, 48)

    position = status.get("position") or 0
    duration = status.get("duration") or 0
    progress_rect = VIDEO_HERO_SEEK
    pygame.draw.rect(s, (58, 58, 58), progress_rect, border_radius=5)
    if duration:
        ratio = max(0.0, min(1.0, float(position) / max(1.0, float(duration))))
        if ratio:
            fill = pygame.Rect(progress_rect.x, progress_rect.y,
                               max(3, int(progress_rect.width * ratio)), 8)
            pygame.draw.rect(s, (236, 236, 236), fill, border_radius=5)
    _text(s, tiny, _video_clock(position), (422, 315), MUTED, 92)
    _text(s, tiny, _video_clock(duration) if duration else "--:--",
          (689, 315), MUTED, 69)

def draw_dashboard(s,font,small,tiny,active_page,station,metadata,playing,
                   bible_playing,bible_paused,bible_name,volume,station_data=None,youtube_playing=False,loaded_logo=None,video_status=None):
    """Render native 800x480 screen; no fixed 320px UI stretching."""
    scenic_background(s)
    pygame.draw.rect(s,(0,0,0),(0,0,800,55))
    pygame.draw.line(s,(48,48,48),(0,54),(800,54))
    _icon(s,"radio",pygame.Rect(15,7,38,38),29)
    _text(s,font,"PiRadio Pro",(55,12),GOLD)
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),WHITE,320)
    _text(s,tiny,"7-inch  |  Wi-Fi",(670,20),MUTED,120)
    pygame.draw.rect(s,(0,0,0),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        r=NAV_RECTS[name]
        selected=(name=="HOME" and active_page=="menu") or (name=="RADIO" and active_page=="radio")
        _glow_card(s,r,(36,36,36) if selected else (12,12,12),(125,125,125) if selected else (48,48,48),14)
        _icon(s,icon,pygame.Rect(r.x+7,r.y+5,28,28),20,WHITE)
        _text(s,small,name.title(),(r.x+39,r.y+8),WHITE,90)
    # Distinct Home launcher and Radio player, both in the same themed shell.
    import datetime, math
    now=datetime.datetime.now()
    active_video = video_status if video_status and video_status.get("playing") else None
    if active_page=="radio" and active_video:
        draw_video_hero(s, font, small, tiny, active_video)
    elif active_page=="radio":
        art=pygame.Rect(163,79,225,265)
        main=pygame.Rect(399,79,384,265)
        _glow_card(s,art,(16,16,16),(58,58,58),20)
        _glow_card(s,main,(16,16,16),(58,58,58),20)
        _station_art(s,pygame.Rect(190,109,170,170),station_data,loaded_logo)
        _text(s,small,"TC RADIOS",(212,300),WHITE,145)
        _text(s,tiny,"LIVE RADIO",(422,100),MUTED,175)
        _text(s,font,station,(422,135),WHITE,340)
        _text(s,small,metadata or "Live streaming",(422,180),MUTED,335)
        for rect,icon in ((PREV,"prev"),(PAUSE,"pause" if playing else "play"),(NEXT,"next")):
            _icon(s,icon,rect,30,WHITE)
        pygame.draw.rect(s,(48,48,48),pygame.Rect(420,292,332,12),border_radius=6)
        pygame.draw.rect(s,(96,165,250),pygame.Rect(420,292,round(332*max(0,min(100,volume))/100),12),border_radius=6)
        _text(s,tiny,f"VOLUME {volume}%",(421,314),MUTED,230)
    else:
        clock=pygame.Rect(158,73,405,260)
        info=pygame.Rect(575,73,211,260)
        _glow_card(s,clock,(16,16,16),(58,58,58),22)
        _glow_card(s,info,(16,16,16),(58,58,58),22)
        time_font=pygame.font.SysFont("dejavusans",100,bold=True)
        time_label=time_font.render(now.strftime("%H:%M"),True,WHITE)
        s.blit(time_label,time_label.get_rect(center=(clock.centerx,168)))
        date_label=small.render(now.strftime("%A, %d %b %Y"),True,WHITE)
        s.blit(date_label,date_label.get_rect(center=(clock.centerx,245)))
        _text(s,tiny,"HOME  •  QUICK ACCESS",(184,298),MUTED,330)
        _text(s,small,"NOW PLAYING",(593,111),MUTED,177)
        _text(s,small,
              (active_video.get("title") or "YouTube video") if active_video else
              (bible_name if bible_playing else station),
              (593,156),WHITE,177)
        _text(s,tiny,
              ("YouTube · Audio only" if active_video.get("minimized") else "YouTube video")
              if active_video else ("Bible audio" if bible_playing else (metadata or "Live radio")),
              (593,205),MUTED,175)
        for i,name in enumerate(CARDS):
            rect=CARD_RECTS[name]
            _card(s,rect,12)
            _icon(s,CARD_ICONS[i],pygame.Rect(rect.x+5,rect.y+5,33,33),22,GOLD)
            _text(s,small,name.title(),(rect.x+42,rect.y+10),WHITE,100)
    _glow_card(s,MINI,(17,17,17),(65,65,65),16)
    
    if active_video or bible_playing or youtube_playing:
        _icon(s,"youtube" if active_video else ("bible" if bible_playing else "youtube"),
              pygame.Rect(166,410,43,43),29,WHITE)
    else:
        _station_art(s,pygame.Rect(166,410,43,43),station_data)
    _text(s,small,(active_video.get("title") or "YouTube video") if active_video
          else (bible_name if bible_playing else station),(218,410),WHITE,385)
    _text(s,tiny,
          ("Paused" if active_video.get("paused") else
           ("YouTube · Audio only" if active_video.get("minimized") else "YouTube video"))
          if active_video else ("Tamil Bible" if bible_playing else (metadata or "Now playing")),
          (218,436),MUTED,385)
    for rect,icon in ((MINI_PREV,"prev"),(MINI_PAUSE,"pause" if playing else "play"),(MINI_NEXT,"next")):
        _icon(s,icon,rect,25,WHITE)
    return True

def hit(pos):
    """Resolve exactly one target for a touch-down."""
    for name,rect in NAV_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    for name,rect in CARD_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    if MINI_OPEN.collidepoint(pos):return ("open_player",None)
    for name,rect in (("prev",PREV),("pause",PAUSE),("next",NEXT),
                      ("prev",MINI_PREV),("pause",MINI_PAUSE),("next",MINI_NEXT)):
        if rect.collidepoint(pos):return ("audio",name)
    if VOLUME.inflate(0,26).collidepoint(pos):return ("volume",max(0,min(100,round((pos[0]-VOLUME.x)*100/VOLUME.width))))
    return None

def draw_shell(s,font,small,tiny,active_page,station,metadata,playing,bible_playing,bible_name,station_data=None,youtube_playing=False,video_status=None):
    """Persistent top bar, left navigation, and bottom mini-player."""
    scenic_background(s)
    pygame.draw.rect(s,(0,0,0),(0,0,800,55))
    pygame.draw.line(s,BORDER if False else (48,48,48),(0,54),(800,54))
    _text(s,font,"PiRadio Pro",(22,12),GOLD)
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),WHITE,360)
    pygame.draw.rect(s,(0,0,0),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        rect=NAV_RECTS[name]
        target={"HOME":"menu","RADIO":"radio","BIBLE":"bible","YOUTUBE":"youtube",
                "FAVORITES":"favorites","CLOCK":"clock","WEATHER":"forecast","SETTINGS":"settings"}[name]
        selected=(active_page==target or (name=="YOUTUBE" and active_page=="youtube_player"))
        _glow_card(s,rect,(36,36,36) if selected else (12,12,12),(125,125,125) if selected else (48,48,48),12)
        _icon(s,icon,pygame.Rect(rect.x+7,rect.y+5,28,28),20,WHITE)
        _text(s,small,name.title(),(rect.x+39,rect.y+8),WHITE,90)
    _glow_card(s,MINI,(17,17,17),(65,65,65),16)

    active_video = video_status if video_status and video_status.get("playing") else None
    if active_video or bible_playing or youtube_playing:
        _icon(s,"youtube" if active_video else ("bible" if bible_playing else "youtube"),
              pygame.Rect(166,410,43,43),28,WHITE)
    else:
        _station_art(s,pygame.Rect(166,410,43,43),station_data)
    _text(s,small,(active_video.get("title") or "YouTube video") if active_video
          else (bible_name if bible_playing else station),(218,410),WHITE,380)
    _text(s,tiny,
          ("Paused" if active_video.get("paused") else
           ("YouTube · Audio only" if active_video.get("minimized") else "YouTube video"))
          if active_video else ("Tamil Bible" if bible_playing else (metadata or "Now playing")),
          (218,436),MUTED,380)
    for rect,icon in ((MINI_PREV,"prev"),(MINI_PAUSE,"pause" if playing else "play"),(MINI_NEXT,"next")):
        _icon(s,icon,rect,25,WHITE)

# Unified minimized-mpv transport panel, shared by every PiRadio page.
# This overlays the normal radio mini-player only when an mpv video is
# minimized. No separate player is created: all actions operate existing mpv.
VIDEO_MINI = pygame.Rect(157, 399, 629, 65)
VIDEO_SEEK = pygame.Rect(215, 451, 273, 11)
VIDEO_BUTTONS = (
    ("seek_relative", -10, pygame.Rect(497, 407, 51, 43), "-10"),
    ("pause", None, pygame.Rect(551, 407, 51, 43), "⏯"),
    ("seek_relative", 10, pygame.Rect(605, 407, 51, 43), "+10"),
    ("restore", None, pygame.Rect(659, 407, 59, 43), "FULL"),
    ("stop", None, pygame.Rect(721, 407, 59, 43), "STOP"),
)


def _video_time(seconds):
    try:
        seconds = max(0, int(float(seconds or 0)))
    except (ValueError, TypeError):
        seconds = 0
    return f"{seconds // 60}:{seconds % 60:02d}"


def draw_video_mini(surface, font, small, tiny, status):
    """Overlay actual minimized-video controls on the 800x480 Pi screen."""
    if not status.get("playing") or not status.get("minimized"):
        return False

    pygame.draw.rect(surface, (15, 15, 15), VIDEO_MINI, border_radius=15)
    pygame.draw.rect(surface, (128, 128, 128), VIDEO_MINI, 2, border_radius=15)
    pygame.draw.circle(surface, (245, 245, 245), (182, 426), 12)
    _text(surface, tiny,
          "YT" if status.get("source", "youtube_video") == "youtube_video" else "GC",
          (171, 418), (0, 0, 0), 23)
    _text(surface, small, status.get("title") or "YouTube video",
          (211, 406), WHITE, 274)
    position = status.get("position", 0) or 0
    duration = status.get("duration", 0) or 0
    label = (
        ("Paused" if status.get("paused") else "Audio playing") +
        "  •  " + _video_time(position) + " / " +
        (_video_time(duration) if duration else "--:--")
    )
    _text(surface, tiny, label, (214, 429), MUTED, 268)
    pygame.draw.rect(surface, (65, 65, 65), VIDEO_SEEK, border_radius=5)
    if duration:
        ratio = max(0.0, min(1.0, float(position) / max(1.0, float(duration))))
        if ratio > 0:
            fill = pygame.Rect(VIDEO_SEEK.x, VIDEO_SEEK.y,
                               max(3, int(VIDEO_SEEK.width * ratio)), VIDEO_SEEK.height)
            pygame.draw.rect(surface, (228, 228, 228), fill, border_radius=5)
    for action, value, rect, label in VIDEO_BUTTONS:
        fill = (85, 37, 37) if action == "stop" else (35, 35, 35)
        pygame.draw.rect(surface, fill, rect, border_radius=9)
        pygame.draw.rect(surface, (92, 92, 92), rect, 1, border_radius=9)
        visible = "II" if action == "pause" and not status.get("paused") else (
            "PLAY" if action == "pause" else label
        )
        text_font = tiny if len(visible) > 2 else small
        rendered = text_font.render(visible, True, WHITE)
        surface.blit(rendered, rendered.get_rect(center=rect.center))
    return True


def video_mini_hit(pos, status):
    """Action tuple or None; consume every touch on the video mini panel."""
    if not status.get("playing") or not status.get("minimized"):
        return None
    if not VIDEO_MINI.collidepoint(pos):
        return None
    for action, value, rect, _label in VIDEO_BUTTONS:
        if rect.collidepoint(pos):
            return action, value
    if VIDEO_SEEK.inflate(0, 12).collidepoint(pos):
        duration = float(status.get("duration") or 0)
        if duration > 0:
            ratio = max(0, min(1, (pos[0] - VIDEO_SEEK.x) / VIDEO_SEEK.width))
            return "seek", duration * ratio
    if pos[0] < 497 and pos[1] < VIDEO_SEEK.y:
        return "restore", None
    return "consume", None


def shell_hit(pos):
    if MINI_OPEN.collidepoint(pos):return ("open_player",None)
    for name,rect in NAV_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    for name,rect in (("prev",MINI_PREV),("pause",MINI_PAUSE),("next",MINI_NEXT)):
        if rect.collidepoint(pos):return ("audio",name)
    return None

# Full-width landscape YouTube search keyboard; key actions use legacy handlers.
KEYBOARD_KEYS=[]
def draw_youtube_keyboard(s,font,small,tiny,query,keys,search_rect,close_rect,go_rect):
    global KEYBOARD_KEYS
    KEYBOARD_KEYS=[]
    panel=pygame.Rect(158,72,628,316)
    _glow_card(s,panel,(16,16,16),(66,66,66),18)
    _text(s,font,"Search YouTube",(179,82),WHITE,390)
    field=pygame.Rect(179,122,492,43)
    _glow_card(s,field,(35,35,35),(85,85,85),11)
    _text(s,small,query or "Enter a video or song name",(191,133),WHITE if query else MUTED,455)
    go=pygame.Rect(683,122,84,43)
    _glow_card(s,go,(25,83,147),(100,170,245),11)
    _text(s,small,"GO",(706,133),WHITE)
    KEYBOARD_KEYS.append((go,go_rect.center))
    rows=("1234567890","qwertyuiop","asdfghjkl","zxcvbnm")
    lookup={value:rect.center for label,value,rect in keys}
    for row_index,row in enumerate(rows):
        count=len(row)+(1 if row_index==3 else 0)
        gap=5
        key_width=min(53,(588-(count-1)*gap)//count)
        total=count*key_width+(count-1)*gap
        x=179+(588-total)//2
        y=176+row_index*39
        for letter in row:
            rect=pygame.Rect(x,y,key_width,34)
            _glow_card(s,rect,(39,39,39),(76,76,76),7)
            label=tiny.render(letter.upper(),True,WHITE)
            s.blit(label,label.get_rect(center=rect.center))
            KEYBOARD_KEYS.append((rect,lookup[letter]))
            x+=key_width+gap
        if row_index==3:
            rect=pygame.Rect(x,y,key_width,34)
            _glow_card(s,rect,(75,51,30),(125,92,60),7)
            _text(s,tiny,"DEL",(rect.x+9,rect.y+8),WHITE)
            KEYBOARD_KEYS.append((rect,lookup["backspace"]))
    for title,action,x,w in (("SPACE","space",179,278),("SEARCH","search",467,190),("DONE","close",667,100)):
        rect=pygame.Rect(x,335,w,40)
        _glow_card(s,rect,(27,72,125) if action=="search" else (38,38,38),(90,90,90),9)
        label=small.render(title,True,WHITE)
        s.blit(label,label.get_rect(center=rect.center))
        KEYBOARD_KEYS.append((rect,close_rect.center if action=="close" else lookup[action]))
def youtube_keyboard_hit(pos):
    for rect,target in KEYBOARD_KEYS:
        if rect.collidepoint(pos):return target
    return None
