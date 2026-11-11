"""Native PiRadio 7 Audio Visualizer Pro, 800×480, no fake spectrum."""
import pygame

BG=(0,0,0)
INK=(246,248,250)
MUTED=(162,171,177)
ACCENT=(75,218,227)
PANEL=pygame.Rect(19,75,762,383)
BACK=pygame.Rect(678,86,88,42)


def draw(surface,font,small,tiny,spectrum,media):
    surface.fill(BG,pygame.Rect(0,65,800,415))
    pygame.draw.rect(surface,(18,21,24),PANEL,border_radius=20)
    pygame.draw.rect(surface,(65,72,76),PANEL,1,border_radius=20)
    label=font.render("AUDIO VISUALIZER PRO",True,INK)
    surface.blit(label,(37,91))
    pygame.draw.rect(surface,(49,55,59),BACK,border_radius=12)
    surf=small.render("HOME",True,INK)
    surface.blit(surf,surf.get_rect(center=BACK.center))
    source=media.get("source") or "radio"
    if source not in ("radio","bible","youtube_audio","guest_audio"):
        status="Music visualizer is available for audio playback"
    elif not (media.get("playing") or media.get("paused")):
        status="Start Radio, Bible, or YouTube audio"
    else:
        status=spectrum.get("message") or "Listening"
    title=str(media.get("title") or "PiRadio")
    while title and font.size(title)[0]>720:
        title=title[:-1]
    surface.blit(font.render(title,True,INK),(37,139))
    status_surface=tiny.render(status[:83],True,MUTED)
    surface.blit(status_surface,(38,173))
    levels=spectrum.get("levels") or ()
    if source not in ("radio","bible","youtube_audio","guest_audio") or not media.get("playing"):
        levels=()
    # Only actual monitor amplitudes are drawn; zero PCM renders a zero line.
    count=24
    base_y=418
    width=27
    spacing=31
    for i in range(count):
        x=34+i*spacing
        level=max(0.0,min(1.0,float(levels[i]))) if i<len(levels) else 0.0
        height=round(level*199)
        pygame.draw.rect(surface,(40,48,52),pygame.Rect(x,base_y-200,width,200),
                         border_radius=5)
        if height:
            pygame.draw.rect(surface,ACCENT,
                             pygame.Rect(x,base_y-height,width,height),
                             border_radius=5)
    pygame.draw.line(surface,(116,129,135),(36,425),(761,425),1)
    return True


def hit(pos):
    if BACK.collidepoint(pos):
        return ("page","menu")
    return None
