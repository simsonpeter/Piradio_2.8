"""Native 800x480 Pearl White Pro radio dashboard for official Pi touchscreen.
Pygame only; audio playback remains owned by touch_radio.py.
"""
import pygame
from ios_ipod_ui import raised_card, THEMES
from fa_icons import draw_icon

BG=(207,221,239); INK=(18,37,69); MUTED=(73,98,134)
BLUE=(18,99,206); NAVY=(12,43,94); WHITE=(239,246,255)
GOLD=(246,191,77)
SKY=(10,39,79)
def scenic_background(s):
    """Lightweight scenic gradient, rendered locally without external image dependencies."""
    for y in range(480):
        k=y/479
        col=(int(8+55*k),int(31+52*k),int(75+45*k))
        pygame.draw.line(s,col,(0,y),(799,y))
    pygame.draw.polygon(s,(15,47,86),[(0,270),(100,211),(200,263),(337,185),(440,253),(560,169),(680,239),(800,186),(800,480),(0,480)])
    pygame.draw.polygon(s,(24,66,104),[(0,345),(130,267),(240,319),(386,238),(503,327),(648,243),(800,318),(800,480),(0,480)])
    pygame.draw.circle(s,(246,173,83),(690,96),32)
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
    scenic_background(s)
    pygame.draw.rect(s,(9,38,78),(0,0,800,55))
    pygame.draw.line(s,(212,223,239),(0,54),(800,54))
    _icon(s,"radio",pygame.Rect(15,7,38,38),29)
    _text(s,font,"PiRadio Pro",(55,12),GOLD)
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),WHITE,320)
    _text(s,tiny,"7-inch  |  Wi-Fi",(670,20),MUTED,120)
    pygame.draw.rect(s,(8,37,79),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        r=NAV_RECTS[name]
        selected=(name=="HOME" and active_page=="menu") or (name=="RADIO" and active_page=="radio")
        if selected:pygame.draw.rect(s,BLUE,r,border_radius=12)
        else:pygame.draw.rect(s,(18,69,124),r,border_radius=12)
        _icon(s,icon,pygame.Rect(r.x+7,r.y+8,28,28),20,WHITE if selected else BLUE)
        _text(s,tiny,name,(r.x+40,r.y+14),WHITE,84)
    # Distinct Home launcher and Radio player, both in the same themed shell.
    import datetime, math
    now=datetime.datetime.now()
    if active_page=="radio":
        art=pygame.Rect(163,79,225,265)
        main=pygame.Rect(399,79,384,265)
        pygame.draw.rect(s,(9,49,109),art,border_radius=20)
        pygame.draw.rect(s,(16,76,147),main,border_radius=20)
        pygame.draw.circle(s,(32,159,225),(275,197),84)
        pygame.draw.circle(s,(10,64,127),(275,197),34)
        _text(s,small,"TC RADIOS",(212,300),WHITE,145)
        _text(s,tiny,"LIVE RADIO",(422,100),(178,219,255),175)
        _text(s,font,station,(422,135),WHITE,340)
        _text(s,small,metadata or "Live streaming",(422,180),(200,229,255),335)
        for rect,icon in ((PREV,"prev"),(PAUSE,"pause" if playing else "play"),(NEXT,"next")):
            _icon(s,icon,rect,30,WHITE)
        pygame.draw.rect(s,(44,118,189),pygame.Rect(420,292,332,12),border_radius=6)
        pygame.draw.rect(s,(35,185,238),pygame.Rect(420,292,round(332*max(0,min(100,volume))/100),12),border_radius=6)
        _text(s,tiny,f"VOLUME {volume}%",(421,314),(206,232,255),230)
    else:
        clock=pygame.Rect(158,73,405,260)
        info=pygame.Rect(575,73,211,260)
        pygame.draw.rect(s,(7,42,102),clock,border_radius=22)
        pygame.draw.rect(s,(18,100,195),info,border_radius=22)
        time_font=pygame.font.Font(None,118)
        time_label=time_font.render(now.strftime("%H:%M"),True,WHITE)
        s.blit(time_label,time_label.get_rect(center=(clock.centerx,168)))
        date_label=small.render(now.strftime("%A, %d %b %Y"),True,WHITE)
        s.blit(date_label,date_label.get_rect(center=(clock.centerx,245)))
        _text(s,tiny,"HOME  •  QUICK ACCESS",(184,298),(184,215,252),330)
        _text(s,small,"NOW PLAYING",(593,111),(195,223,255),177)
        _text(s,small,bible_name if bible_playing else station,(593,156),WHITE,177)
        _text(s,tiny,"Bible audio" if bible_playing else (metadata or "Live radio"),(593,205),(199,225,255),175)
        for i,name in enumerate(CARDS):
            rect=CARD_RECTS[name]
            _card(s,rect,12)
            _icon(s,CARD_ICONS[i],pygame.Rect(rect.x+5,rect.y+5,33,33),22,BLUE)
            _text(s,tiny,name,(rect.x+42,rect.y+14),INK,100)
    pygame.draw.rect(s,(5,35,83),MINI,border_radius=16)
    pygame.draw.rect(s,GOLD,MINI,2,border_radius=16)
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
    scenic_background(s)
    pygame.draw.rect(s,(9,38,78),(0,0,800,55))
    pygame.draw.line(s,BORDER if False else (212,223,239),(0,54),(800,54))
    _text(s,font,"PiRadio Pro",(22,12),GOLD)
    _text(s,tiny,"Radio  •  Tamil Bible  •  YouTube",(225,20),WHITE,360)
    pygame.draw.rect(s,(8,37,79),SIDEBAR)
    for name,icon in zip(NAV,NAV_ICONS):
        rect=NAV_RECTS[name]
        target={"HOME":"menu","RADIO":"radio","BIBLE":"bible","YOUTUBE":"youtube",
                "FAVORITES":"favorites","CLOCK":"clock","SETTINGS":"settings"}[name]
        selected=active_page==target
        pygame.draw.rect(s,GOLD if selected else (18,69,124),rect,border_radius=12)
        _icon(s,icon,pygame.Rect(rect.x+7,rect.y+8,28,28),20,WHITE if selected else BLUE)
        _text(s,tiny,name,(rect.x+40,rect.y+14),INK if selected else WHITE,84)
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
