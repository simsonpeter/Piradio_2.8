"""Native 800x480 Pearl White Pro radio dashboard for official Pi touchscreen.
Pygame only; audio playback remains owned by touch_radio.py.
"""
import pygame
from ios_ipod_ui import raised_card, THEMES
from fa_icons import draw_icon

BG=(237,242,250); INK=(24,40,68); MUTED=(98,115,143)
BLUE=(23,110,225); NAVY=(13,48,105); WHITE=(255,255,255)
SIDEBAR=pygame.Rect(0,55,145,425)
NAV=("HOME","RADIO","BIBLE","YOUTUBE","FAVORITES","CLOCK","SETTINGS")
NAV_ICONS=("library","radio","bible","youtube","favorites","clock","settings")
CARDS=("RADIO","BIBLE","YOUTUBE","FAVORITES")
CARD_ICONS=("radio","bible","youtube","favorites")
NAV_RECTS={n:pygame.Rect(8,67+i*49,130,44) for i,n in enumerate(NAV)}
CARD_RECTS={n:pygame.Rect(157+i*157,295,149,82) for i,n in enumerate(CARDS)}
PREV=pygame.Rect(445,195,54,54)
PAUSE=pygame.Rect(525,186,72,72)
NEXT=pygame.Rect(623,195,54,54)
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
    pygame.draw.rect(s,(209,221,238),rect.move(0,3),border_radius=radius)
    pygame.draw.rect(s,WHITE,rect,border_radius=radius)
    pygame.draw.rect(s,(218,229,242),rect,1,border_radius=radius)

def draw_dashboard(s,font,small,tiny,active_page,station,metadata,playing,
                   bible_playing,bible_paused,bible_name,volume):
    """Render native 800x480 screen; no fixed 320px UI stretching."""
    s.fill(BG)
    pygame.draw.rect(s,WHITE,(0,0,800,55))
    pygame.draw.line(s,(212,223,239),(0,54),(800,54))
    _icon(s,"radio",pygame.Rect(15,7,38,38),29)
    _text(s,font,"PiRadio Pro",(55,12))
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),MUTED,320)
    _text(s,tiny,"7-inch  |  Wi-Fi",(670,20),MUTED,120)
    pygame.draw.rect(s,(227,235,248),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        r=NAV_RECTS[name]
        selected=(name=="HOME" and active_page=="menu") or (name=="RADIO" and active_page=="radio")
        if selected:pygame.draw.rect(s,BLUE,r,border_radius=12)
        else:_card(s,r,12)
        _icon(s,icon,pygame.Rect(r.x+7,r.y+8,28,28),20,WHITE if selected else BLUE)
        _text(s,tiny,name,(r.x+40,r.y+14),WHITE if selected else INK,84)
    _card(s,MAIN,19)
    pygame.draw.rect(s,(20,64,129),ARTWORK,border_radius=17)
    pygame.draw.circle(s,(40,122,224),ARTWORK.center,65)
    _icon(s,"radio",ARTWORK,75,WHITE)
    _text(s,small,"TC RADIOS",(193,240),WHITE,145)
    current=bible_name if bible_playing else station
    _text(s,tiny,"TAMIL AUDIO BIBLE" if bible_playing else "LIVE RADIO",(377,93),BLUE)
    _text(s,font,current,(376,122),INK,395)
    _text(s,small,("Paused" if bible_paused else "Bible chapter playing") if bible_playing else (metadata or "Live stream"),(376,154),MUTED,395)
    for i in range(38):
        h=5+((i*11+7)%22)
        pygame.draw.rect(s,(94,168,240),(377+i*10,180-h,6,h),border_radius=2)
    for rect,icon in ((PREV,"prev"),(PAUSE,"pause" if playing else "play"),(NEXT,"next")):
        pygame.draw.rect(s,BLUE if rect==PAUSE else (233,240,250),rect,border_radius=rect.height//2)
        _icon(s,icon,rect,30,WHITE if rect==PAUSE else NAVY)
    _icon(s,"volume",pygame.Rect(384,260,28,28),20,NAVY)
    pygame.draw.rect(s,(213,224,240),VOLUME,border_radius=8)
    fill=pygame.Rect(VOLUME.x,VOLUME.y,max(4,int(VOLUME.width*max(0,min(100,volume))/100)),VOLUME.height)
    pygame.draw.rect(s,BLUE,fill,border_radius=8)
    _text(s,tiny,f"{volume}%",(672,268),MUTED)
    for i,name in enumerate(CARDS):
        rect=CARD_RECTS[name]
        _card(s,rect,15)
        _icon(s,CARD_ICONS[i],pygame.Rect(rect.centerx-20,rect.y+9,40,35),28,BLUE)
        label=tiny.render(name,True,INK)
        s.blit(label,label.get_rect(center=(rect.centerx,rect.y+62)))
    pygame.draw.rect(s,NAVY,MINI,border_radius=16)
    _icon(s,"bible" if bible_playing else "radio",pygame.Rect(166,410,43,43),29,WHITE)
    _text(s,small,current,(218,410),WHITE,385)
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
