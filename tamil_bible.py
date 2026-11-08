"""Tamil Audio Bible module for PiRadio. Separate VLC player, persistent book/chapter."""
import json
from pathlib import Path
import pygame
from fa_icons import draw_icon
from ios_ipod_ui import raised_card
import vlc

NAMES = ("Genesis Exodus Leviticus Numbers Deuteronomy Joshua Judges Ruth").split()+[
"1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job","Psalms","Proverbs","Ecclesiastes","Song of Songs","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah","Haggai","Zechariah","Malachi","Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians","Colossians","1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation"]
COUNTS=[50,40,27,36,34,24,21,4,31,24,22,25,29,36,10,13,10,42,150,31,12,8,66,52,5,48,12,14,3,9,1,4,7,3,3,3,2,14,4,28,16,24,21,28,16,16,13,6,6,4,4,5,3,6,4,3,1,13,5,5,3,5,1,1,1,22]
SLUGS=[n.replace(" ","_") for n in NAMES]
SLUGS[21]="Song_Of_Solomon"
BASE="https://info2.sermon-online.com/tamil/Bible/Tamil-Audio_Bible_Complete_OT_NT_MP3/"
STATE=Path.home()/".piradio_tamil_bible.json"

class BiblePlayer:
    def __init__(self):
        self.book=0;self.chapter=1;self.list_page=0;self.selecting=False
        self.player=vlc.MediaPlayer();self.playing=False;self.started=False
        self.status="Choose PLAY";self.last_state=None;self.paused=False
        try:
            data=json.loads(STATE.read_text())
            self.book=max(0,min(65,int(data.get("book",0))))
            self.chapter=max(1,min(COUNTS[self.book],int(data.get("chapter",1))))
        except (OSError,ValueError,TypeError):pass
    def save(self):
        try:STATE.write_text(json.dumps({"book":self.book,"chapter":self.chapter}))
        except OSError:pass
    def url(self):
        return BASE+f"{self.book+1:02d}{self.chapter:03d}-The_Book_Of_{SLUGS[self.book]}_Chapter-{self.chapter:03d}.mp3"
    def stop(self):
        self.player.stop();self.playing=False;self.paused=False;self.started=False;self.status="Stopped"
    def play(self,stop_radio=None):
        if stop_radio:stop_radio()
        self.player.stop()
        self.player.set_media(vlc.Media(self.url()))
        self.player.play()
        self.playing=True;self.paused=False;self.started=False;self.status="Loading chapter..."
        self.save()
    def toggle_pause(self):
        if not self.playing:
            return
        self.player.set_pause(0 if self.paused else 1)
        self.paused=not self.paused
        self.status="Paused" if self.paused else "Playing"
    def shift(self,delta,stop_radio=None):
        if delta>0:
            if self.chapter<COUNTS[self.book]:self.chapter+=1
            else:self.book=(self.book+1)%66;self.chapter=1
        else:
            if self.chapter>1:self.chapter-=1
            else:self.book=(self.book-1)%66;self.chapter=COUNTS[self.book]
        self.save()
        if self.playing:self.play(stop_radio)
    def tick(self,stop_radio=None):
        if not self.playing:return
        state=self.player.get_state()
        if state==vlc.State.Playing:self.started=True;self.paused=False;self.status="Playing"
        elif state==vlc.State.Paused:self.paused=True;self.status="Paused"
        elif state==vlc.State.Error:self.stop();self.status="Stream unavailable"
        elif state==vlc.State.Ended and self.started:self.shift(1,stop_radio)
    def render(self,screen,font,small,mode="dark"):
        """iPod-style Bible screen; existing touch targets and VLC engine retained."""
        light = mode == "light"
        bg = (231,235,241) if light else (12,17,30)
        card = (255,255,255) if light else (29,39,58)
        ink = (29,41,57) if light else (247,249,253)
        muted = (103,115,131) if light else (160,175,195)
        blue = (64,104,176) if light else (111,155,223)
        gold = (220,156,54)
        screen.fill(bg)
        def label(s, y, f=small, color=None):
            img=f.render(s,True,color or ink)
            screen.blit(img,((320-img.get_width())//2,y))
        def btn(rect,title,highlight=False):
            if highlight:
                pygame.draw.rect(screen,blue,rect,border_radius=15)
            else:
                raised_card(screen,rect,mode,15,2)
            color=(255,255,255) if highlight else ink
            img=small.render(title,True,color)
            screen.blit(img,img.get_rect(center=rect.center))
        label("TAMIL AUDIO BIBLE",12,small,gold)
        if self.selecting:
            for i in range(8):
                b=self.list_page*8+i
                if b>=66:break
                btn(pygame.Rect(14,48+i*44,292,40),f"{b+1}. {NAMES[b]}",b==self.book)
            btn(pygame.Rect(12,414,92,44),"BACK")
            btn(pygame.Rect(113,414,92,44),"< LIST")
            btn(pygame.Rect(214,414,92,44),"LIST >")
            return
        raised_card(screen,pygame.Rect(14,48,292,174),mode,20,4)
        pygame.draw.circle(screen,blue,(160,109),36)
        draw_icon(screen, "bible", (160,109), 37, (255,255,255))
        pygame.draw.rect(screen,(255,255,255),(145,91,30,36),3,border_radius=4)
        pygame.draw.line(screen,(255,255,255),(160,93),(160,123),2)
        label(NAMES[self.book],152,font)
        label(f"CHAPTER {self.chapter} / {COUNTS[self.book]}",185,small,muted)
        label(self.status,216,small,gold)
        for rect,title,highlight in [
            ((12,235,92,50),"< BOOK",False),((114,235,92,50),"BOOKS",False),
            ((216,235,92,50),"BOOK >",False),
            ((12,301,92,52),"PREV",False),
            ((114,301,92,52),"RESUME" if self.paused else ("PAUSE" if self.playing else "PLAY"),True),
            ((216,301,92,52),"NEXT",False),
            ((62,404,196,48),"HOME",False)]:
            button_rect = pygame.Rect(*rect)
            if title in ("PREV", "NEXT", "PLAY", "PAUSE", "RESUME"):
                if highlight:
                    pygame.draw.rect(screen,blue,button_rect,border_radius=15)
                else:
                    raised_card(screen,button_rect,mode,15,2)
                icon = {"PREV":"prev","NEXT":"next","PLAY":"play",
                        "PAUSE":"pause","RESUME":"play"}[title]
                draw_icon(screen, icon, button_rect.center, 25,
                          (255,255,255) if highlight else ink)
            else:
                btn(button_rect,title,highlight)
        label(f"{self.book+1} OF 66 BOOKS",370,small,muted)
    def touch(self,pos,stop_radio=None):
        x,y=pos
        if self.selecting:
            if y>=414:
                if x<108:self.selecting=False
                elif x<210:self.list_page=max(0,self.list_page-1)
                else:self.list_page=min(8,self.list_page+1)
            elif 48<=y<400:
                idx=self.list_page*8+(y-48)//44
                if idx<66:
                    was_playing=self.playing
                    self.book=idx;self.chapter=1;self.selecting=False;self.save()
                    if was_playing:self.play(stop_radio)
            return False
        if 235<=y<290:
            if x<108:self.book=(self.book-1)%66;self.chapter=1
            elif x<210:self.list_page=self.book//8;self.selecting=True;return False
            else:self.book=(self.book+1)%66;self.chapter=1
            self.save()
            if self.playing:self.play(stop_radio)
        elif 301<=y<358:
            if x<108:self.shift(-1,stop_radio)
            elif x<210:
                if self.playing:self.toggle_pause()
                else:self.play(stop_radio)
            else:self.shift(1,stop_radio)
        elif y>=404:return True
        return False
