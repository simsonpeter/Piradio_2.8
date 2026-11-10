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

YOUTUBE_SEEK = pygame.Rect(385, 290, 365, 12)
YOUTUBE_ART = pygame.Rect(185, 128, 178, 177)


def _time_label(ms):
    try:
        seconds = max(0, int(float(ms or 0) / 1000))
    except (ValueError, OverflowError, TypeError):
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (f"{hours}:{minutes:02d}:{seconds:02d}"
            if hours else f"{minutes}:{seconds:02d}")


def youtube_player(s, font, small, tiny, **v):
    """Real dedicated YouTube Now Playing panel, independent of TCRADIOS."""
    status = v.get("youtube_status") or {}
    title_text = str(status.get("title") or "Choose a YouTube song")[:180]
    uploader = str(status.get("uploader") or "YouTube · Audio & video")[:90]
    is_active = bool(status.get("active"))
    paused = bool(status.get("paused"))
    mpv_video = bool(status.get("video"))
    length = max(0, float(status.get("length_ms") or 0))
    position = max(0, float(status.get("position_ms") or 0))
    can_video = bool(v.get("video_available"))

    _text(s, tiny, "YOUTUBE  /  NOW PLAYING", (182, 106), (190, 190, 190), 320)
    button(s, tiny, "SEARCH / RESULTS", pygame.Rect(604, 76, 158, 39),
           ("yt", "search"))

    # Dedicated artwork tile: intentionally never uses a TCRADIOS station logo.
    pygame.draw.rect(s, (21, 21, 21), YOUTUBE_ART, border_radius=17)
    pygame.draw.rect(s, (74, 74, 74), YOUTUBE_ART, 1, border_radius=17)
    picture = v.get("youtube_artwork")
    if picture is not None:
        try:
            rect = pygame.Rect(191, 134, 166, 165)
            width, height = picture.get_size()
            ratio = max(rect.width / max(1, width),
                        rect.height / max(1, height))
            image = pygame.transform.smoothscale(
                picture,
                (max(1, int(width * ratio)), max(1, int(height * ratio)))
            )
            clipped = image.subsurface(
                ((image.get_width() - rect.width) // 2,
                 (image.get_height() - rect.height) // 2,
                 rect.width, rect.height)
            )
            s.blit(clipped, rect.topleft)
        except (pygame.error, ValueError, AttributeError):
            picture = None
    if picture is None:
        pygame.draw.circle(s, (47, 47, 47), YOUTUBE_ART.center, 59)
        pygame.draw.circle(s, (219, 219, 219), YOUTUBE_ART.center, 58, 2)
        pygame.draw.polygon(
            s, (246, 246, 246),
            [(249, 193), (249, 239), (285, 216)]
        )
    TARGETS[tuple(YOUTUBE_ART)] = ("yt", "video")

    _text(s, font, title_text, (386, 139), TEXT, 370)
    _text(s, tiny, uploader, (387, 187), MUTED, 355)
    if mpv_video:
        playing_state = "VIDEO PAUSED" if paused else "VIDEO PLAYING"
    elif is_active:
        playing_state = "PAUSED" if paused else "AUDIO PLAYING"
    else:
        playing_state = "READY TO PLAY"
    pygame.draw.circle(s, (94, 215, 193) if is_active and not paused
                       else (148, 148, 148), (398, 244), 5)
    _text(s, tiny, playing_state, (414, 233), MUTED, 270)

    pygame.draw.rect(s, (60, 60, 60), YOUTUBE_SEEK, border_radius=6)
    if length:
        progress = min(1.0, position / length)
        width = int(YOUTUBE_SEEK.width * progress)
        if width:
            pygame.draw.rect(
                s, (233, 233, 233),
                pygame.Rect(YOUTUBE_SEEK.x, YOUTUBE_SEEK.y,
                            max(3, width), YOUTUBE_SEEK.height),
                border_radius=6
            )
    TARGETS[tuple(YOUTUBE_SEEK.inflate(0, 22))] = ("yt", "seek")
    _text(s, tiny, _time_label(position), (386, 308), MUTED, 100)
    end_text = _time_label(length) if length else "--:--"
    _text(s, tiny, end_text, (707, 308), MUTED, 57)

    button(s, tiny, "VIDEO" if can_video else "AUDIO",
           pygame.Rect(185, 324, 178, 49),
           ("yt", "video") if can_video else None,
           active=can_video)
    for x, width, label, action in (
        (383, 68, "PREV", "previous"),
        (459, 59, "-10s", "back10"),
        (526, 90, "PLAY" if not is_active or paused else "PAUSE", "toggle"),
        (623, 59, "+10s", "forward10"),
        (690, 72, "NEXT", "next"),
    ):
        button(s, tiny, label, pygame.Rect(x, 324, width, 49),
               ("yt", action), active=(action == "toggle"))
    if not is_active:
        _text(s, tiny, "Tap PLAY to start your last YouTube selection",
              (385, 263), MUTED, 358)


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
        temperature=str(v.get("temp"))+"°C" if v.get("temp") is not None else "--°C"
        t=font.render(temperature,True,(248,252,255))
        s.blit(t,t.get_rect(center=(weather.centerx,202)))
        city=tiny.render(str(v.get("city","")),True,MUTED)
        s.blit(city,city.get_rect(center=(weather.centerx,252)))
        _text(s,tiny,"NOW PLAYING  •  "+str(v.get("station","")),(200,337),MUTED,535)
    elif page=="forecast":
        _text(s,small,"WEATHER & 5-DAY FORECAST",(181,115),TEXT,560)
        city=str(v.get("city") or "Selected location")
        _text(s,tiny,city.upper(),(184,152),MUTED,480)
        temperature=str(v.get("temp")) if v.get("temp") is not None else "--"
        if temperature.endswith("°C"):temperature=temperature[:-2]
        big=pygame.font.Font(None,105)
        shown=big.render(temperature+"°",True,WHITE)
        s.blit(shown,(190,172))
        _text(s,small,str(v.get("weather_type") or "Current conditions").replace("_"," ").title(),(405,211),TEXT,330)
        forecast=v.get("forecast",[])
        for i,day in enumerate(forecast[:5]):
            x=182+i*116
            rect=pygame.Rect(x,280,106,86)
            pygame.draw.rect(s,(35,35,35),rect,border_radius=12)
            pygame.draw.rect(s,(88,88,88),rect,1,border_radius=12)
            if isinstance(day,dict):
                dayname=str(day.get("date") or day.get("day") or f"Day {i+1}")[-5:]
                high=day.get("high",day.get("max",day.get("temperature_2m_max","--")))
                low=day.get("low",day.get("min",day.get("temperature_2m_min","--")))
            else:
                dayname=f"DAY {i+1}";high="--";low="--"
            _text(s,tiny,dayname,(x+10,294),MUTED,86)
            _text(s,tiny,f"{high}° / {low}°",(x+9,328),TEXT,91)
        if not forecast:
            _text(s,tiny,"Forecast will appear after weather data loads",(183,349),MUTED,555)
        status_text = str(v.get("weather_status") or "")[:150]
        if status_text:
            _text(s,tiny,status_text,(184,386),MUTED,558)
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
        player_view = bool(v.get("youtube_player_view"))
        if player_view:
            youtube_player(s, font, small, tiny, **v)
        else:
            # Results remain accessible without replacing or stopping audio.
            player_available = bool(v.get("youtube_status", {}).get("title")
                                    or v.get("video_available"))
            if player_available:
                button(s, tiny, "NOW PLAYING", pygame.Rect(609, 76, 153, 37),
                       ("yt", "player"), active=True)
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
                _text(s,tiny,
                      f"RESULTS {offset+1}-{offset+len(visible)} OF {len(results)}",
                      (314,351),MUTED,330)
            else:
                presets=v.get("presets",[])
                for i,item in enumerate(presets[:6]):
                    name=item[0] if isinstance(item,(tuple,list)) else str(item)
                    button(s,tiny,name,
                           pygame.Rect(180+(i%3)*194,182+(i//3)*57,181,48),
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
