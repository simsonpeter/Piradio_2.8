-- PiRadio Pro: large touch controls over the fullscreen mpv video.
local mp = require 'mp'
local assdraw = require 'mp.assdraw'
local function draw()
    local w,h = mp.get_osd_size()
    if not w or w <= 0 or not h or h <= 0 then return end
    local ass = assdraw.ass_new()
    local labels = {'PLAY / PAUSE', 'MINIMISE', 'EXIT'}
    for i=1,3 do
        local x = (i-0.5)*w/3
        ass:new_event()
        ass:pos(x,h-35)
        ass:append('{\\an2\\fs25\\bord4\\shad2\\1c&HFFFFFF&\\3c&H111111&}'..labels[i])
    end
    mp.set_osd_ass(w,h,ass.text)
end
local function minimize()
    -- Do not minimize the PiRadio SDL window; only mpv's own video window.
    mp.set_property('vid','no')
    mp.set_property('window-minimized','yes')
end
local function tap()
    local w,h=mp.get_osd_size()
    local p=mp.get_mouse_pos()
    if not p or not w or w<=0 or not h or h<=0 then return end
    if p.y < h-110 then return end
    if p.x < w/3 then
        mp.commandv('cycle','pause')
    elseif p.x < w*2/3 then
        minimize()
    else
        mp.command('quit')
    end
end
mp.add_forced_key_binding('MBTN_LEFT','piradio-touch',tap)
mp.add_key_binding('m','piradio-minimise',minimize)
mp.add_key_binding('ESC','piradio-exit',function() mp.command('quit') end)
mp.register_event('file-loaded',draw)
mp.observe_property('osd-width','number',draw)
mp.observe_property('osd-height','number',draw)
