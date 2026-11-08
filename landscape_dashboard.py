"""Native 800x480 Pearl White Pro radio dashboard for official Pi touchscreen.
Pygame only; audio playback remains owned by touch_radio.py.
"""
import pygame
from ios_ipod_ui import raised_card, THEMES
from fa_icons import draw_icon

BG=(207,221,239); INK=(18,37,69); MUTED=(73,98,134)
BLUE=(18,99,206); NAVY=(12,43,94); WHITE=(239,246,255)
SIDEBAR=pygame.Rect(0,55,145,425)
NAV=("HOME","RADIO","BIBLE","YOUTUBE","FAVORITES","CLOCK","SETTINGS")
NAV_ICONS=("library","radio","bible","youtube","favorites","clock","settings")
CARDS=("RADIO","BIBLE","YOUTUBE","FAVORITES")
CARD_ICONS=("radio","bible","youtube","favorites")
NAV_RECTS={n:pygame.Rect(8,67+i*49,130,44) for i,n in enumerate(NAV)}
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

def _card(s,rect,radius=14):
    pygame.draw.rect(s,(155,180,214),rect.move(0,3),border_radius=radius)
    pygame.draw.rect(s,WHITE,rect,border_radius=radius)
    pygame.draw.rect(s,(168,192,223),rect,1,border_radius=radius)

def draw_dashboard(s,font,small,tiny,active_page,station,metadata,playing,
                   bible_playing,bible_paused,bible_name,volume):
    """Render native 800x480 screen; no fixed 320px UI stretching."""
    s.fill(BG)
    pygame.draw.rect(s,(222,235,252),(0,0,800,55))
    pygame.draw.line(s,(212,223,239),(0,54),(800,54))
    _icon(s,"radio",pygame.Rect(15,7,38,38),29)
    _text(s,font,"PiRadio Pro",(55,12))
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),MUTED,320)
    _text(s,tiny,"7-inch  |  Wi-Fi",(670,20),MUTED,120)
    pygame.draw.rect(s,(174,199,233),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        r=NAV_RECTS[name]
        selected=(name=="HOME" and active_page=="menu") or (name=="RADIO" and active_page=="radio")
        if selected:pygame.draw.rect(s,BLUE,r,border_radius=12)
        else:_card(s,r,12)
        _icon(s,icon,pygame.Rect(r.x+7,r.y+8,28,28),20,WHITE if selected else BLUE)
        _text(s,tiny,name,(r.x+40,r.y+14),WHITE if selected else INK,84)
    # Shared cinematic blue dashboard: true native 800x480 coordinates.
    # Reserve 399..464 for the persistent mini-player.
    import datetime
    now=datetime.datetime.now()
    clock=pygame.Rect(158,73,405,298)
    weather=pygame.Rect(575,73,211,298)
    pygame.draw.rect(s,(7,42,102),clock,border_radius=22)
    pygame.draw.rect(s,(18,100,195),weather,border_radius=22)
    time_font=pygame.font.Font(None,112)
    time_label=time_font.render(now.strftime("%H:%M"),True,WHITE)
    s.blit(time_label,time_label.get_rect(center=(clock.centerx,168)))
    date_label=small.render(now.strftime("%A, %d %b %Y"),True,WHITE)
    s.blit(date_label,date_label.get_rect(center=(clock.centerx,233)))
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(197,287),(184,215,252),330)
    _text(s,small,"NOW PLAYING",(596,106),(195,223,255),165)
    _text(s,small,bible_name if bible_playing else station,(596,147),WHITE,170)
    _text(s,tiny,"Paused" if bible_paused else ("Bible audio" if bible_playing else (metadata or "Live radio")),(596,183),(199,225,255),172)
    _text(s,tiny,"PiRadio Pro",(596,292),(204,230,255),175)
    for rect,icon in ((PREV,"prev"),(PAUSE,"pause" if playing else "play"),(NEXT,"next")):
        display_rect=pygame.Rect(588+(0 if icon=="prev" else 64 if icon in ("pause","play") else 128),226,49,48)
        _icon(s,icon,display_rect,26,WHITE)
    for i,name in enumerate(CARDS):
        rect=pygame.Rect(158+i*158,346,150,43)
        _card(s,rect,12)
        _icon(s,CARD_ICONS[i],pygame.Rect(rect.x+5,rect.y+5,33,33),22,BLUE)
        _text(s,tiny,name,(rect.x+42,rect.y+14),INK,100)
    pygame.draw.rect(s,NAVY,MINI,border_radius=16)
    _icon(s,"bible" if bible_playing else "radio",pygame.Rect(166,410,43,43),29,WHITE)
    _text(s,small,bible_name if bible_playing else station,(218,410),WHITE,385)
    _text(s,tiny,"Tamil Bible" if bible_playing else (metadata or "Now playing"),(218,436),(181,209,248),385)
    for rect,icon in ((MINI_PREV,"prev"),(MINI_PAUSE,"pause" if playing else "play"),(MINI_NEXT,"next")):
        _icon(s,icon,rect,25,WHITE)
    return True

def hit(pos):
    """Resolve exactly one target for a touch-down."""
    for name,rect in NAV_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    for name,rect in CARD_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    for name,rect in (("prev",PREV),("pause",PAUSE),("next",NEXT),
                      ("prev",MINI_PREV),("pause",MINI_PAUSE),("next",MINI_NEXT)):
        if rect.collidepoint(pos):return ("audio",name)
    if VOLUME.inflate(0,26).collidepoint(pos):return ("volume",max(0,min(100,round((pos[0]-VOLUME.x)*100/VOLUME.width))))
    return None

def draw_shell(s,font,small,tiny,active_page,station,metadata,playing,bible_playing,bible_name):
    """Persistent top bar, left navigation, and bottom mini-player."""
    s.fill(BG)
    pygame.draw.rect(s,WHITE,(0,0,800,55))
    pygame.draw.line(s,BORDER if False else (212,223,239),(0,54),(800,54))
    _text(s,font,"PiRadio Pro",(22,12))
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),MUTED,360)
    pygame.draw.rect(s,(227,235,248),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        rect=NAV_RECTS[name]
        target={"HOME":"menu","RADIO":"radio","BIBLE":"bible","YOUTUBE":"youtube",
                "FAVORITES":"favorites","CLOCK":"clock","SETTINGS":"settings"}[name]
        selected=active_page==target
        pygame.draw.rect(s,BLUE if selected else WHITE,rect,border_radius=12)
        _icon(s,icon,pygame.Rect(rect.x+7,rect.y+8,28,28),20,WHITE if selected else BLUE)
        _text(s,tiny,name,(rect.x+40,rect.y+14),WHITE if selected else INK,84)
    pygame.draw.rect(s,NAVY,MINI,border_radius=16)
    _icon(s,"bible" if bible_playing else "radio",pygame.Rect(166,410,43,43),28,WHITE)
    _text(s,small,bible_name if bible_playing else station,(218,410),WHITE,380)
    _text(s,tiny,"Tamil Bible" if bible_playing else (metadata or "Now playing"),(218,436),(181,209,248),380)
    for rect,icon in ((MINI_PREV,"prev"),(MINI_PAUSE,"pause" if playing else "play"),(MINI_NEXT,"next")):
        _icon(s,icon,rect,25,WHITE)

def shell_hit(pos):
    for name,rect in NAV_RECTS.items():
        if rect.collidepoint(pos):return ("page",name)
    for name,rect in (("prev",MINI_PREV),("pause",MINI_PAUSE),("next",MINI_NEXT)):
        if rect.collidepoint(pos):return ("audio",name)
    return None
