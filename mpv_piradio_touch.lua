-- PiRadio 7-inch landscape fullscreen video controls.
-- Touch video to reveal controls; hide after five seconds of inactivity.
local mp = require 'mp'
local assdraw = require 'mp.assdraw'
local visible = false
local dragging = false
local hide_timer
local last_width, last_height = 800, 480

local function fmt(s)
    if not s or s < 0 then return '--:--' end
    s = math.floor(s)
    return string.format('%d:%02d', math.floor(s / 60), s % 60)
end
local function duration()
    return mp.get_property_number('duration', 0) or 0
end
local function layout(w,h)
    local bar_y = h - math.max(112, math.floor(h * 0.25))
    return bar_y, w * 0.10, w * 0.90
end
local function draw()
    local w,h = mp.get_osd_size()
    if not w or w <= 0 or not h or h <= 0 then return end
    last_width,last_height = w,h
    if not visible then mp.set_osd_ass(w,h,''); return end
    local ass = assdraw.ass_new()
    local y,left,right = layout(w,h)
    local pos = mp.get_property_number('time-pos',0) or 0
    local total = duration()
    local ratio = total > 0 and math.max(0, math.min(1,pos/total)) or 0
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(0,%d)\\1c&H101010&\\alpha&H35&}\\p1 m 0 0 l %d 0 %d %d 0 %d\\p0',y-18,w,w,h-y+18,h-y+18))
    local function label(x,yy,t,fs)
        ass:new_event()
        ass:pos(x,yy)
        ass:append(string.format('{\\an5\\fs%d\\bord2\\shad0\\1c&HFFFFFF&\\3c&H111111&}',fs or 22)..t)
    end
    label(w/2,y-2,fmt(pos)..' / '..fmt(total),20)
    local track_y = y+30
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(0,0)\\bord0\\1c&H777777&}\\p1 m %.1f %.1f l %.1f %.1f %.1f %.1f %.1f %.1f\\p0',left,track_y,right,track_y,right,track_y+8,left,track_y+8))
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(0,0)\\bord0\\1c&HFFFFFF&}\\p1 m %.1f %.1f l %.1f %.1f %.1f %.1f %.1f %.1f\\p0',left,track_y,left+(right-left)*ratio,track_y,left+(right-left)*ratio,track_y+8,left,track_y+8))
    local labels = {'-10s','PLAY / PAUSE','+10s','MINIMISE','EXIT'}
    for i,t in ipairs(labels) do label((i-0.5)*w/5,h-29,t,math.max(15,math.floor(w/48))) end
    mp.set_osd_ass(w,h,ass.text)
end
local function schedule_hide()
    if hide_timer then hide_timer:kill() end
    hide_timer = mp.add_timeout(5,function()
        if dragging then schedule_hide() else visible=false; draw() end
    end)
end
local function show()
    visible=true
    draw()
    schedule_hide()
end
local function minimize()
    mp.set_property('vid','no')
    mp.set_property('window-minimized','yes')
    visible=false
    draw()
end
local function seek_at(x)
    local w,h=mp.get_osd_size()
    if not w or w<=0 then return end
    local _,left,right=layout(w,h)
    local total=duration()
    if total>0 then
        mp.commandv('seek',total*math.max(0,math.min(1,(x-left)/(right-left))),'absolute','exact')
    end
end
local function tap()
    local p=mp.get_mouse_pos()
    local w,h=mp.get_osd_size()
    if not p or not w or w<=0 then return end
    if not visible then show(); return end
    local y,left,right=layout(w,h)
    if p.y>=y+15 and p.y<=y+55 and p.x>=left-15 and p.x<=right+15 then
        dragging=true
        seek_at(p.x)
    elseif p.y>=h-65 then
        local index=math.min(5,math.floor(p.x/(w/5))+1)
        if index==1 then mp.commandv('seek',-10,'relative')
        elseif index==2 then mp.commandv('cycle','pause')
        elseif index==3 then mp.commandv('seek',10,'relative')
        elseif index==4 then minimize()
        elseif index==5 then mp.command('quit') end
    end
    if visible then show() end
end
local function move()
    if not dragging then return end
    local p=mp.get_mouse_pos()
    if p then seek_at(p.x); show() end
end
local function release()
    if dragging then dragging=false; schedule_hide() end
end
mp.add_forced_key_binding('MBTN_LEFT','piradio-touch',tap)
mp.add_forced_key_binding('MBTN_LEFT_UP','piradio-touch-release',release)
mp.add_forced_key_binding('MOUSE_MOVE','piradio-touch-drag',move)
mp.add_key_binding('m','piradio-minimise',minimize)
mp.add_key_binding('ESC','piradio-exit',function() mp.command('quit') end)
mp.register_event('file-loaded',function() visible=false; draw() end)
mp.observe_property('time-pos','number',function() if visible then draw() end end)
mp.observe_property('duration','number',function() if visible then draw() end end)
mp.observe_property('osd-width','number',draw)
mp.observe_property('osd-height','number',draw)
