"""Native 800x480 Tamil Bible screen and deterministic touch hitboxes."""
import pygame
from tamil_bible import NAMES, COUNTS
from fa_icons import draw_icon

BG=(237,242,250); WHITE=(255,255,255); INK=(24,40,68)
MUTED=(99,115,140); BLUE=(23,110,225); BORDER=(211,225,241)
BUTTONS={
 "home":pygame.Rect(674,12,108,46),
 "book_prev":pygame.Rect(38,331,130,52),
 "books":pygame.Rect(183,331,132,52),
 "book_next":pygame.Rect(330,331,130,52),
 "prev":pygame.Rect(498,203,80,65),
 "play":pygame.Rect(594,195,84,80),
 "next":pygame.Rect(695,203,80,65),
 "bookmark":pygame.Rect(498,294,133,54),
 "speed":pygame.Rect(647,294,128,54),
 "list_back":pygame.Rect(38,405,135,54),
 "list_prev":pygame.Rect(330,405,135,54),
 "list_next":pygame.Rect(481,405,135,54),
}
def card(s,r):
    pygame.draw.rect(s,WHITE,r,border_radius=17)
    pygame.draw.rect(s,BORDER,r,1,border_radius=17)
def label(s,f,text,rect,color=INK):
    txt=str(text)
    while txt and f.render(txt,True,color).get_width()>rect.width-12:txt=txt[:-1]
    surf=f.render(txt,True,color)
    s.blit(surf,surf.get_rect(center=rect.center))
def button(s,f,name,text,selected=False):
    r=BUTTONS[name]
    pygame.draw.rect(s,BLUE if selected else WHITE,r,border_radius=14)
    pygame.draw.rect(s,BLUE if selected else BORDER,r,1,border_radius=14)
    label(s,f,text,r,WHITE if selected else INK)
def draw(s,player,font,small,tiny):
    s.fill(BG)
    pygame.draw.rect(s,WHITE,(0,0,800,70))
    label(s,font,"TAMIL AUDIO BIBLE",pygame.Rect(24,9,400,52))
    button(s,small,"home","HOME")
    if player.selecting:
        card(s,pygame.Rect(20,85,760,305))
        for i in range(12):
            idx=player.list_page*12+i
            if idx>=66:break
            col=i%3;row=i//3
            rect=pygame.Rect(38+col*247,101+row*69,229,58)
            pygame.draw.rect(s,BLUE if idx==player.book else BG,rect,border_radius=12)
            label(s,small,f"{idx+1}. {NAMES[idx]}",rect,WHITE if idx==player.book else INK)
        button(s,small,"list_back","BACK")
        button(s,small,"list_prev","PREVIOUS")
        button(s,small,"list_next","NEXT")
        return
    card(s,pygame.Rect(20,85,445,315))
    pygame.draw.circle(s,BLUE,(242,161),49)
    draw_icon(s,"bible",(242,161),47,WHITE)
    label(s,font,NAMES[player.book],pygame.Rect(35,222,415,46))
    label(s,small,f"CHAPTER {player.chapter} / {COUNTS[player.book]}",pygame.Rect(35,268,415,38),MUTED)
    for name,text in (("book_prev","< BOOK"),("books","BOOKS"),("book_next","BOOK >")):
        button(s,small,name,text)
    card(s,pygame.Rect(482,85,298,305))
    label(s,small,player.status,pygame.Rect(500,105,264,45),MUTED)
    for name,icon in (("prev","prev"),("play","play" if not player.playing or player.paused else "pause"),("next","next")):
        r=BUTTONS[name]
        pygame.draw.rect(s,BLUE if name=="play" else BG,r,border_radius=18)
        draw_icon(s,icon,r.center,31,WHITE if name=="play" else BLUE)
    button(s,tiny,"bookmark","SAVED" if [player.book,player.chapter] in player.bookmarks else "BOOKMARK")
    button(s,tiny,"speed",f"{player.speed:g}x SPEED")
    card(s,pygame.Rect(20,414,760,52))
    label(s,tiny,f"Now selected: {NAMES[player.book]}  •  Chapter {player.chapter}",pygame.Rect(32,417,735,46),MUTED)
def hit(player,pos,stop_radio=None):
    if BUTTONS["home"].collidepoint(pos):return "home"
    if player.selecting:
        if BUTTONS["list_back"].collidepoint(pos):player.selecting=False
        elif BUTTONS["list_prev"].collidepoint(pos):player.list_page=max(0,player.list_page-1)
        elif BUTTONS["list_next"].collidepoint(pos):player.list_page=min(5,player.list_page+1)
        else:
            for i in range(12):
                idx=player.list_page*12+i
                if idx<66 and pygame.Rect(38+(i%3)*247,101+(i//3)*69,229,58).collidepoint(pos):
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
