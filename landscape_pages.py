"""Native secondary panels for 800x480 landscape PiRadio.
No portrait surface scaling. Hit targets map to existing legacy actions.
"""
import pygame
from datetime import datetime
from landscape_dashboard import WHITE,_card,_text,_icon
TEXT=(250,250,250)
MUTED=(190,190,190)
ACCENT=(96,165,250)
PANEL=pygame.Rect(160,65,625,322)
TARGETS={}
BLUETOOTH_PAGE=0
BLUETOOTH_PAGE_SIZE=6
BLUETOOTH_DEVICE_COUNT=0
def title(s,f,text):
    _text(s,f,text,(181,77),TEXT,550)
def button(s,font,text,rect,target=None,active=False):
    _card(s,rect,13)
    if active:pygame.draw.rect(s,(37,99,235),rect,border_radius=13)
    label_text=str(text)
    while label_text and font.render(label_text,True,TEXT).get_width()>rect.width-16:
        label_text=label_text[:-1]
    if label_text!=str(text) and label_text:
        label_text=label_text[:-1]+"…"
    label=font.render(label_text,True,TEXT)
    s.blit(label,label.get_rect(center=rect.center))
    if target is not None:TARGETS[(rect.x,rect.y,rect.w,rect.h)]=target
def draw(s,page,font,small,tiny,**v):
    TARGETS.clear()
    _card(s,PANEL,18)
    pygame.draw.rect(s,(23,23,23),PANEL.inflate(-10,-10),border_radius=15)
    title(s,font,page.upper())
    if page=="clock":
        now=datetime.now()
        clock_box=pygame.Rect(179,119,578,240)
        pygame.draw.rect(s,(22,22,22),clock_box,border_radius=23)
        pygame.draw.rect(s,(65,65,65),clock_box,2,border_radius=23)
        # Render at native 800x480 resolution; never enlarge a portrait clock.
        big=pygame.font.Font(None,142)
        time_surface=big.render(now.strftime("%H:%M"),True,(248,252,255))
        s.blit(time_surface,time_surface.get_rect(center=(445,205)))
        date=small.render(now.strftime("%A, %d %B %Y").upper(),True,MUTED)
        s.blit(date,date.get_rect(center=(445,290)))
        weather=pygame.Rect(615,149,128,150)
        pygame.draw.rect(s,(32,32,32),weather,border_radius=16)
        temperature=str(v.get("temp","--"))+"°C"
        t=font.render(temperature,True,(248,252,255))
        s.blit(t,t.get_rect(center=(weather.centerx,202)))
        city=tiny.render(str(v.get("city","")),True,MUTED)
        s.blit(city,city.get_rect(center=(weather.centerx,252)))
        _text(s,tiny,"NOW PLAYING  •  "+str(v.get("station","")),(200,337),MUTED,535)
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
        _text(s,small,"SOUND OUTPUT",(180,127),TEXT)
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
    elif page=="bluetooth":
        global BLUETOOTH_PAGE, BLUETOOTH_DEVICE_COUNT
        devices=v.get("devices",[])
        BLUETOOTH_DEVICE_COUNT=len(devices)
        total_pages=max(1,(len(devices)+BLUETOOTH_PAGE_SIZE-1)//BLUETOOTH_PAGE_SIZE)
        BLUETOOTH_PAGE=min(BLUETOOTH_PAGE,total_pages-1)
        _text(s,small,"BLUETOOTH SPEAKERS",(180,117),TEXT)
        button(s,small,"SEARCH DEVICES" if not v.get("busy") else "SEARCHING...",pygame.Rect(535,92,224,51),(160,96))
        _text(s,tiny,str(v.get("bt_status","")),(182,154),MUTED,570)
        offset=BLUETOOTH_PAGE*BLUETOOTH_PAGE_SIZE
        for i,device in enumerate(devices[offset:offset+BLUETOOTH_PAGE_SIZE]):
            x=180+(i%2)*296
            y=182+(i//2)*57
            rect=pygame.Rect(x,y,281,49)
            name=device.get("name") or device.get("address","Unknown device")
            state="CONNECTED" if device.get("connected") else ("CONNECT" if device.get("paired") else "PAIR")
            # Map each visible device to the legacy six-row hit targets.
            button(s,tiny,name,rect,(160,163+i*46),active=device.get("connected",False))
            _text(s,tiny,state,(x+10,y+32),MUTED,250)
        if not devices:_text(s,small,"Tap SEARCH DEVICES to find your speaker",(185,210),MUTED,540)
        button(s,tiny,"PREV",pygame.Rect(180,345,102,36),("bt_page",-1))
        _text(s,tiny,f"PAGE {BLUETOOTH_PAGE+1} / {total_pages}  -  {len(devices)} DEVICES",(304,354),MUTED,242)
        button(s,tiny,"NEXT",pygame.Rect(548,345,99,36),("bt_page",1))
        button(s,tiny,"BACK",pygame.Rect(662,345,98,36),(160,448))
    elif page=="youtube":
        results=v.get("youtube_results",[])
        offset=v.get("youtube_offset",0)
        button(s,small,"SEARCH YOUTUBE",pygame.Rect(180,117,450,49),(120,92))
        button(s,small,"GO",pygame.Rect(643,117,120,49),(285,92))
        if results:
            visible=results[offset:offset+4]
            for i,video in enumerate(visible):
                r=pygame.Rect(180,175+i*43,580,39)
                name=video.get("title") or video.get("name") or "YouTube audio"
                button(s,tiny,f"{offset+i+1}. {name}",r,(160,266+i*44))
            _text(s,tiny,f"RESULTS {offset+1}-{offset+len(visible)} OF {len(results)}",(314,351),MUTED,330)
        else:
            presets=v.get("presets",[])
            for i,item in enumerate(presets[:6]):
                name=item[0] if isinstance(item,(tuple,list)) else str(item)
                button(s,tiny,name,pygame.Rect(180+(i%3)*194,182+(i//3)*57,181,48),
                       (62+(i%3)*102,150+(i//3)*36))
            _text(s,tiny,str(v.get("status","")),(310,350),MUTED,390)
        button(s,tiny,"◀ PREV",pygame.Rect(180,343,116,38),(42,224))
        button(s,tiny,"NEXT ▶",pygame.Rect(647,343,116,38),(278,224))
    else:
        _text(s,small,"Select an option from the sidebar",(180,168),MUTED,530)
def hit(pos):
    global BLUETOOTH_PAGE
    for coords,target in TARGETS.items():
        if pygame.Rect(*coords).collidepoint(pos):
            if isinstance(target,tuple) and target[0]=="bt_page":
                last=max(0,(BLUETOOTH_DEVICE_COUNT-1)//BLUETOOTH_PAGE_SIZE)
                BLUETOOTH_PAGE=max(0,min(last,BLUETOOTH_PAGE+target[1]))
                return ("bt_navigation",)
            return target
    return None
