-- PiRadio Pro fullscreen video touch controls for mpv.
local mp = require 'mp'
local assdraw = require 'mp.assdraw'
local visible = true
local function button_text()
    local w,h=mp.get_osd_size()
    if w==0 or h==0 then return end
    local ass=assdraw.ass_new()
    ass:new_event()
    ass:append('{\\an2\\fs24\\bord2\\shad1\\1c&HFFFFFF&\\3c&H111111&}')
    ass:pos(w/2,h-34)
    ass:append('  [  PAUSE / PLAY  ]      [  MINIMISE  ]      [  EXIT  ]  ')
    mp.set_osd_ass(w,h,ass.text)
end
local function click()
    local w,h=mp.get_osd_size()
    local p=mp.get_mouse_pos()
    if not p or not w or w==0 or not h or h==0 then return end
    if p.y<h-85 then return end
    if p.x<w*0.39 then
        mp.commandv('cycle','pause')
    elseif p.x<w*0.72 then
        mp.set_property('vid','no')
        mp.set_property('window-minimized','yes')
    else
        mp.command('quit')
    end
end
mp.add_forced_key_binding('MBTN_LEFT','piradio-touch',click)
mp.register_event('file-loaded',button_text)
mp.observe_property('osd-width','number',button_text)
mp.observe_property('osd-height','number',button_text)
