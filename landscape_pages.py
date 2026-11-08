"""Native secondary panels for 800x480 landscape PiRadio.
No portrait surface scaling. Hit targets map to existing legacy actions.
"""
import pygame
from datetime import datetime
from landscape_dashboard import BG,BLUE,WHITE,INK,MUTED,_card,_text
PANEL=pygame.Rect(160,65,625,322)
TARGETS={}
def title(s,f,text):
    _text(s,f,text,(181,77),INK,550)
def button(s,font,text,rect,target=None,active=False):
    _card(s,rect,13)
    if active:pygame.draw.rect(s,(225,239,255),rect,border_radius=13)
    label=font.render(str(text),True,BLUE if active else INK)
    s.blit(label,label.get_rect(center=rect.center))
    if target is not None:TARGETS[(rect.x,rect.y,rect.w,rect.h)]=target
def draw(s,page,font,small,tiny,**v):
    TARGETS.clear()
    _card(s,PANEL,18)
    pygame.draw.rect(s,(218,232,250),PANEL.inflate(-10,-10),border_radius=15)
    title(s,font,page.upper())
    if page=="clock":
        now=datetime.now()
        clock_box=pygame.Rect(179,119,578,240)
        pygame.draw.rect(s,(19,55,107),clock_box,border_radius=23)
        pygame.draw.rect(s,(34,80,145),clock_box,2,border_radius=23)
        # Render at native 800x480 resolution; never enlarge a portrait clock.
        big=pygame.font.Font(None,142)
        time_surface=big.render(now.strftime("%H:%M"),True,(248,252,255))
        s.blit(time_surface,time_surface.get_rect(center=(445,205)))
        date=small.render(now.strftime("%A, %d %B %Y").upper(),True,(167,205,255))
        s.blit(date,date.get_rect(center=(445,290)))
        weather=pygame.Rect(615,149,128,150)
        pygame.draw.rect(s,(41,94,161),weather,border_radius=16)
        temperature=str(v.get("temp","--"))+"°C"
        t=font.render(temperature,True,(248,252,255))
        s.blit(t,t.get_rect(center=(weather.centerx,202)))
        city=tiny.render(str(v.get("city","")),True,(185,216,255))
        s.blit(city,city.get_rect(center=(weather.centerx,252)))
        _text(s,tiny,"NOW PLAYING  •  "+str(v.get("station","")),(200,337),(190,218,255),535)
    elif page=="favorites":
        button(s,small,"ADD / REMOVE CURRENT",pygame.Rect(515,74,251,51),(160,83))
        fav=v.get("favorites",[]);stations=v.get("stations",[])
        for i in range(6):
            x=179+(i%3)*197;y=141+(i//3)*105
            r=pygame.Rect(x,y,182,88)
            idx=fav[i] if i<len(fav) else None
            station=stations[idx] if idx is not None and idx<len(stations) else {}
            button(s,small,station.get("name","Empty slot"),r,(84+(i%2)*152,155+(i//2)*96) if idx is not None else None)
            if station:_text(s,tiny,station.get("genre","Radio"),(x+14,y+61),MUTED,155)
    elif page=="settings":
        _text(s,small,"SOUND OUTPUT",(180,127),MUTED)
        for i,name in enumerate(("AUTO","JACK","HDMI","BLUETOOTH")):
            button(s,tiny,name,pygame.Rect(180+i*147,155,134,48),(49+i*76,116))
        _text(s,small,"DISPLAY BRIGHTNESS",(180,222),MUTED)
        button(s,small,"−",pygame.Rect(180,249,74,50),(43,208))
        button(s,tiny,"AUTO DIM",pygame.Rect(268,249,178,50),(160,208))
        button(s,small,"+",pygame.Rect(460,249,74,50),(277,208))
        _text(s,small,"THEME",(180,323),MUTED)
        button(s,small,"◀",pygame.Rect(270,311,75,52),(43,303))
        button(s,small,"▶",pygame.Rect(360,311,75,52),(277,303))
        button(s,tiny,"Wi-Fi",pygame.Rect(536,311,108,52),(85,378))
        button(s,tiny,"WEB QR",pygame.Rect(651,311,108,52),(234,378))
    elif page=="youtube":
        _text(s,small,"Search and play YouTube audio",(180,123),MUTED)
        button(s,small,"SEARCH YOUTUBE",pygame.Rect(180,154,365,58),(120,92))
        button(s,small,"GO",pygame.Rect(559,154,198,58),(285,92))
        presets=v.get("presets",[])
        for i,item in enumerate(presets[:6]):
            name=item[0] if isinstance(item,(tuple,list)) else str(item)
            button(s,tiny,name,pygame.Rect(180+(i%3)*194,226+(i//3)*57,181,48),
                   (62+(i%3)*102,150+(i//3)*36))
        button(s,small,"‹",pygame.Rect(180,342,62,39),(42,224))
        button(s,small,"›",pygame.Rect(695,342,62,39),(278,224))
        _text(s,tiny,str(v.get("status","")),(260,351),MUTED,415)
    else:
        _text(s,small,"Select an option from the sidebar",(180,168),MUTED,530)
def hit(pos):
    for coords,target in TARGETS.items():
        if pygame.Rect(*coords).collidepoint(pos):return target
    return None
