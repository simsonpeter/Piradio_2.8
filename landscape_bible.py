"""Native 800x480 Tamil Bible screen and deterministic touch hitboxes."""
import pygame
from tamil_bible import NAMES, COUNTS
from fa_icons import draw_icon

BG=(0,0,0); WHITE=(245,245,245); INK=(245,245,245)
MUTED=(184,190,200); BLUE=(37,99,235); BORDER=(65,73,85)
BUTTONS={"home":pygame.Rect(680,80,96,40),"book_prev":pygame.Rect(180,326,166,48),"books":pygame.Rect(353,326,171,48),"book_next":pygame.Rect(531,326,241,48),"prev":pygame.Rect(555,212,60,62),"play":pygame.Rect(623,207,73,73),"next":pygame.Rect(704,212,60,62),"bookmark":pygame.Rect(554,286,105,35),"speed":pygame.Rect(666,286,105,35),"list_back":pygame.Rect(181,341,105,35),"list_prev":pygame.Rect(433,341,105,35),"list_next":pygame.Rect(546,341,105,35)}
LIST_RECTS=[pygame.Rect(183+(i%3)*197,139+(i//3)*47,185,41) for i in range(12)]

def card(s,r):
    pygame.draw.rect(s,(23,23,23),r,border_radius=17)
    pygame.draw.rect(s,BORDER,r,1,border_radius=17)
def label(s,f,text,rect,color=INK):
    txt=str(text)
    while txt and f.render(txt,True,color).get_width()>rect.width-12:txt=txt[:-1]
    surf=f.render(txt,True,color)
    s.blit(surf,surf.get_rect(center=rect.center))
def button(s,f,name,text,selected=False):
    r=BUTTONS[name]
    pygame.draw.rect(s,BLUE if selected else (38,38,38),r,border_radius=14)
    pygame.draw.rect(s,BLUE if selected else BORDER,r,1,border_radius=14)
    label(s,f,text,r,WHITE if selected else INK)
def draw(s,player,font,small,tiny):
    # Draw at native 800x480 coordinates inside the available content region.
    pygame.draw.rect(s,BG,pygame.Rect(165,74,620,310),border_radius=12)
    label(s,font,"TAMIL AUDIO BIBLE",pygame.Rect(181,81,475,43))
    button(s,tiny,"home","HOME")
    if player.selecting:
        label(s,tiny,f"ALL 66 BOOKS - PAGE {player.list_page+1}/6",pygame.Rect(181,116,575,22),MUTED)
        for i,r in enumerate(LIST_RECTS):
            idx=player.list_page*12+i
            if idx>=66:continue
            pygame.draw.rect(s,BLUE if idx==player.book else (37,37,37),r,border_radius=10)
            label(s,tiny,f"{idx+1}. {NAMES[idx]}",r)
        button(s,tiny,"list_back","CLOSE")
        button(s,tiny,"list_prev","PREV")
        button(s,tiny,"list_next","NEXT")
        return
    card(s,pygame.Rect(180,132,358,185))
    pygame.draw.circle(s,BLUE,(234,188),34)
    draw_icon(s,"bible",(234,188),32,WHITE)
    label(s,small,NAMES[player.book],pygame.Rect(275,156,251,53))
    label(s,tiny,f"CHAPTER {player.chapter} / {COUNTS[player.book]}",pygame.Rect(275,210,251,31),MUTED)
    label(s,tiny,"SELECT BOOK BELOW",pygame.Rect(190,267,337,29),MUTED)
    card(s,pygame.Rect(547,132,225,185))
    label(s,tiny,player.status,pygame.Rect(555,147,210,36),MUTED)
    for name,icon in (("prev","prev"),("play","play" if not player.playing or player.paused else "pause"),("next","next")):
        r=BUTTONS[name]
        pygame.draw.rect(s,BLUE if name=="play" else (38,38,38),r,border_radius=15)
        draw_icon(s,icon,r.center,27,WHITE)
    button(s,tiny,"bookmark","BOOKMARK")
    button(s,tiny,"speed",f"{player.speed:g}x SPEED")
    for name,txt in (("book_prev",f"◀ {NAMES[(player.book-1)%66]}"),("books","ALL 66 BOOKS"),("book_next",f"{NAMES[(player.book+1)%66]} ▶")):
        button(s,tiny,name,txt)

def hit(player,pos,stop_radio=None):
    if BUTTONS["home"].collidepoint(pos):return "home"
    if player.selecting:
        if BUTTONS["list_back"].collidepoint(pos):player.selecting=False
        elif BUTTONS["list_prev"].collidepoint(pos):player.list_page=max(0,player.list_page-1)
        elif BUTTONS["list_next"].collidepoint(pos):player.list_page=min(5,player.list_page+1)
        else:
            for i in range(12):
                idx=player.list_page*12+i
                if idx<66 and LIST_RECTS[i].collidepoint(pos):
                    was_playing=player.playing
                    player.book=idx;player.chapter=1;player.selecting=False;player.save()
                    if was_playing:player.play(stop_radio)
                    break
        return None
    for name in ("book_prev","books","book_next","prev","play","next","bookmark","speed"):
        if not BUTTONS[name].collidepoint(pos):continue
        if name=="books":player.list_page=player.book//12;player.selecting=True
        elif name in ("book_prev","book_next"):
            player.book=(player.book+(-1 if name=="book_prev" else 1))%66
            player.chapter=1;player.save()
            if player.playing:player.play(stop_radio)
        elif name=="prev":player.shift(-1,stop_radio)
        elif name=="next":player.shift(1,stop_radio)
        elif name=="play":
            if player.playing:player.toggle_pause()
            else:player.play(stop_radio)
        elif name=="bookmark":player.toggle_bookmark()
        elif name=="speed":player.cycle_speed()
        break
    return None
