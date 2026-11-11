"""Responsive, same-origin Smart Remote 2.0 for PiRadio 7.

This is an additive companion to the existing '/' remote. No competing radio
player is started on the phone. Only the Raspberry Pi owns sound and video.
Guest Cast and Photo Frame retain their separate PIN-protected portals.
"""
REMOTE_V2_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#080a0c">
<title>PiRadio 7 | Smart Remote</title>
<style>
:root {color-scheme:dark;--bg:#090b0e;--surface:#15191e;--inner:#1d2228;--line:#37414a;--text:#f7fafc;--muted:#a9b5bf;--accent:#54d6e2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,"Noto Sans Tamil",sans-serif}
button,input,select{font:inherit}button{cursor:pointer;color:inherit;background:#293139;border:1px solid #48545e;border-radius:13px;min-height:44px;padding:10px 13px;font-weight:650}
button:disabled{opacity:.4;cursor:default}button.primary{background:#edf4f5;color:#101316;border-color:#f6fbfb}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
a{color:var(--text)}.app{max-width:740px;margin:0 auto;padding:calc(16px + env(safe-area-inset-top)) 16px calc(106px + env(safe-area-inset-bottom))}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:19px}
.brand{font-size:22px;font-weight:780;letter-spacing:-.7px}.brand b{color:var(--accent)}.sub{color:var(--muted);font-size:12px}
.online{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:30px;border:1px solid var(--line);font-size:12px}
.dot{display:inline-block;width:8px;height:8px;background:#8a9096;border-radius:50%}.dot.ok{background:#54d6a5}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:21px;padding:17px;margin-bottom:13px}
.kicker{color:var(--accent);font-size:11px;font-weight:750;letter-spacing:1.6px;text-transform:uppercase}
h1,h2,h3,p{margin-top:0}h1{font-size:24px;margin:9px 0 3px;line-height:1.2;overflow-wrap:anywhere}h2{font-size:19px;margin-bottom:14px}
.status{color:var(--muted);font-size:13px;margin-bottom:12px;min-height:18px}
.controls{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:9px;margin:14px 0}
.controls button{font-size:22px;min-height:59px}
.volume-row,.space{display:flex;justify-content:space-between;align-items:center;gap:12px}.volume-row{margin-top:13px}
input[type=range]{width:100%;accent-color:var(--accent);min-height:29px;touch-action:pan-y}
.pill{font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:5px 9px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.grid.triple{grid-template-columns:repeat(3,minmax(0,1fr))}
.tile{background:var(--inner);border:1px solid var(--line);border-radius:14px;padding:13px;min-width:0;display:flex;flex-direction:column;align-items:flex-start;gap:5px;text-align:left}
.tile strong{font-size:14px;overflow-wrap:anywhere}.tile small{color:var(--muted);font-weight:400}
.row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #2f363e}
.row:last-child{border-bottom:0}.grow{flex:1;min-width:0}.row strong{display:block;font-size:14px;overflow-wrap:anywhere}.row small{color:var(--muted)}
.row button{flex-shrink:0}.select-row{display:grid;grid-template-columns:1.3fr .7fr;gap:10px;margin:12px 0}
select,input[type=search]{border:1px solid var(--line);border-radius:12px;background:var(--inner);color:var(--text);width:100%;padding:11px;min-height:46px}
select{appearance:auto}.action-row{display:flex;gap:9px;flex-wrap:wrap}.action-row button{flex:1;min-width:96px}
section.view{display:none}section.view.active{display:block}
.bottom{position:fixed;z-index:8;bottom:0;left:0;right:0;background:rgba(14,17,20,.97);border-top:1px solid var(--line);padding:8px max(12px,calc((100vw - 728px)/2)) calc(8px + env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(5,1fr);gap:5px}
.bottom button{border:0;background:transparent;color:var(--muted);border-radius:10px;min-height:58px;padding:7px 1px;font-size:12px}
.bottom button .ico{font-size:23px;display:block}.bottom button.active{color:var(--accent);background:#193137}
form.search{display:flex;gap:8px;margin-bottom:12px}form.search button{min-width:82px}
#toast{position:fixed;z-index:40;left:50%;bottom:calc(86px + env(safe-area-inset-bottom));transform:translateX(-50%);width:max-content;max-width:90vw;padding:10px 16px;border-radius:13px;border:1px solid #57727a;background:#22343b;color:white;display:none}
#toast.show{display:block}.muted{color:var(--muted)}.linktile{display:flex;align-items:center;justify-content:space-between;text-decoration:none;background:var(--inner);border:1px solid var(--line);border-radius:13px;padding:13px;margin:9px 0}
#video-controls{display:none}.small-btn{padding:7px 11px;min-height:40px}
.weather-number{font-size:56px;font-weight:750;line-height:1.1;margin:5px 0}.forecast{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}.forecast div{text-align:center;background:var(--inner);border-radius:10px;padding:9px 3px;font-size:12px}
@media(max-width:400px){.app{padding-left:12px;padding-right:12px}.panel{padding:14px}.forecast{gap:3px}.grid.triple{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
</head>
<body>
<div class="app">
 <header>
  <div><div class="brand">PiRadio <b>7</b></div><div class="sub">Smart Remote 2.0 · Raspberry Pi</div></div>
  <div class="online"><span id="online-dot" class="dot"></span><span id="connection">Connecting</span></div>
 </header>

 <section class="view active" id="view-home">
  <div class="panel">
   <div class="space"><span class="kicker" id="home-source">NOW PLAYING</span><span class="pill" id="home-status">READY</span></div>
   <h1 id="home-title">Connecting to PiRadio…</h1><div class="status" id="home-detail">Only one player on the Raspberry Pi</div>
   <div class="controls">
    <button id="media-prev" type="button" aria-label="Previous">⏮</button>
    <button id="media-toggle" class="primary" type="button" aria-label="Play or pause">▶</button>
    <button id="media-next" type="button" aria-label="Next">⏭</button>
   </div>
   <div class="volume-row"><strong>Volume</strong><span id="volume-label">--%</span></div>
   <input id="volume-slider" type="range" min="0" max="100" value="60" aria-label="PiRadio volume">
   <div id="home-seek-wrap" hidden>
    <div class="volume-row"><small class="muted">Timeline</small><small id="home-time" class="muted">--:-- / --:--</small></div>
    <input id="home-seek" type="range" min="0" max="100" value="0" step="0.5" aria-label="Seek current video">
   </div>
   <div class="action-row" style="margin-top:12px">
    <button type="button" id="open-cinema">Cinema controls</button>
    <button type="button" id="media-stop">Stop</button>
   </div>
  </div>
  <div class="panel">
   <h2>Quick access</h2>
   <div class="grid">
    <button type="button" class="tile" data-go="radio"><strong>📻 Radio</strong><small>Stations and favourites</small></button>
    <button type="button" class="tile" data-go="bible"><strong>📖 Tamil Bible</strong><small>Books and chapters</small></button>
    <button type="button" class="tile" data-go="video"><strong>▶ YouTube</strong><small>Play on Pi screen</small></button>
    <button type="button" class="tile" data-go="more"><strong>▣ Photo Frame</strong><small>Gallery and weather</small></button>
   </div>
  </div>
 </section>

 <section class="view" id="view-radio">
  <div class="panel"><div class="space"><h2>Radio stations</h2><button id="radio-refresh" type="button" class="small-btn">Refresh</button></div>
   <input id="station-filter" type="search" placeholder="Search stations…" aria-label="Filter radio stations">
   <div id="station-list" style="margin-top:12px"></div>
  </div>
  <div class="panel"><h2>My favourites <span class="pill" id="favourite-count">0/6</span></h2><div id="favourite-list" class="muted">Loading…</div></div>
 </section>

 <section class="view" id="view-bible">
  <div class="panel">
   <div class="kicker">TAMIL AUDIO BIBLE</div><h2 id="bible-current">Current chapter</h2>
   <div id="bible-info" class="status">Loading saved progress…</div>
   <div class="select-row">
    <label>Book<select id="bible-book" aria-label="Bible book"></select></label>
    <label>Chapter<select id="bible-chapter" aria-label="Bible chapter"></select></label>
   </div>
   <div class="action-row"><button type="button" id="bible-play" class="primary">Play chapter</button><button type="button" id="bible-pause">Pause / Resume</button></div>
   <div class="action-row" style="margin-top:9px"><button type="button" id="bible-prev">Previous</button><button type="button" id="bible-next">Next</button><button type="button" id="bible-bookmark">☆ Bookmark</button></div>
   <div style="margin-top:13px" class="muted">Audio and saved progress remain on PiRadio, not on your phone.</div>
  </div>
  <div class="panel"><h2>Saved bookmarks</h2><div id="bible-bookmarks" class="muted">Loading…</div></div>
 </section>

 <section class="view" id="view-video">
  <div class="panel">
   <h2>YouTube on Pi</h2>
   <form id="youtube-form" class="search">
    <input type="search" id="youtube-query" placeholder="Search YouTube…" aria-label="Search YouTube" required>
    <button type="submit" class="primary">Search</button>
   </form>
   <div id="youtube-results" class="muted">Search for a song or video.</div>
  </div>
  <div id="video-controls" class="panel">
   <div class="kicker" id="video-source">PI CINEMA</div>
   <h2 id="video-title" style="margin:7px 0">Current video</h2>
   <div class="space"><small id="video-state" class="muted">Playing</small><small id="video-time" class="muted">--:--</small></div>
   <input type="range" min="0" max="100" value="0" step="0.5" id="video-seek" aria-label="Video timeline">
   <div class="volume-row"><label for="video-volume">Pi volume</label><span id="video-volume-label">--%</span></div>
   <div class="action-row" style="align-items:center;gap:8px;margin-top:3px">
    <button type="button" id="video-volume-down" aria-label="Volume down 5 percent">−</button>
    <input type="range" id="video-volume" min="0" max="100" step="1" value="80" aria-label="Cinema volume" style="flex:1;min-width:0">
    <button type="button" id="video-volume-up" aria-label="Volume up 5 percent">+</button>
   </div>
   <div class="action-row" style="margin:9px 0">
    <button id="video-prev" type="button">-10s</button>
    <button id="video-toggle" class="primary" type="button">Pause</button>
    <button id="video-next" type="button">+10s</button>
   </div>
   <div class="action-row">
    <button id="video-minimize" type="button">Minimise</button>
    <button id="video-restore" type="button">Full screen</button>
    <button id="video-stop" type="button">Stop</button>
   </div>
  </div>
 </section>

 <section class="view" id="view-more">
  <div class="panel">
   <h2>Weather</h2>
   <div class="kicker" id="weather-city">Location</div>
   <div id="weather-temperature" class="weather-number">--°</div>
   <div id="weather-condition" class="status">Loading weather…</div>
   <div id="weather-forecast" class="forecast"></div>
   <button type="button" id="weather-refresh" style="margin-top:13px">Refresh weather</button>
  </div>
  <div class="panel">
   <h2>Media sharing and settings</h2>
   <a class="linktile" href="/frame"><span>▣ Photo Frame gallery</span><span class="muted">Open ›</span></a>
   <a class="linktile" href="/cast"><span>↗ Guest Cast portal</span><span class="muted">Open ›</span></a>
   <a class="linktile" href="/"><span>⚙ Original advanced remote</span><span class="muted">Open ›</span></a>
   <div class="status">Photo uploads and Guest Cast continue to use their separate on-screen pairing PINs.</div>
  </div>
  <div class="panel"><h2>Sleep timer</h2><div class="action-row">
   <button data-sleep="15" type="button">15 min</button>
   <button data-sleep="30" type="button">30 min</button>
   <button data-sleep="60" type="button">60 min</button>
   <button id="sleep-cancel" type="button">Cancel</button>
  </div><div class="status" id="sleep-status" style="margin-top:11px"></div></div>
 </section>
</div>

<nav class="bottom" aria-label="Remote navigation">
 <button data-tab="home" class="active" aria-label="Home"><span class="ico">⌂</span>Home</button>
 <button data-tab="radio" aria-label="Radio"><span class="ico">◉</span>Radio</button>
 <button data-tab="bible" aria-label="Bible"><span class="ico">▤</span>Bible</button>
 <button data-tab="video" aria-label="Video"><span class="ico">▶</span>Video</button>
 <button data-tab="more" aria-label="More"><span class="ico">☷</span>More</button>
</nav>
<div id="toast" role="status" aria-live="polite"></div>

<script>
"use strict";
const state = {session:null,stations:[],favorites:[],bible:null,video:null,tab:"home",
 seekEditing:false,volumeEditing:false,videoEditing:false,cinemaVolumeEditing:false,pollBusy:false};
const $ = id => document.getElementById(id);
const sources = {radio:"INTERNET RADIO",youtube_audio:"YOUTUBE AUDIO",youtube_video:"YOUTUBE VIDEO",
 bible:"TAMIL BIBLE",guest_audio:"PHONE AUDIO",guest_video:"PHONE VIDEO",
 guest_photos:"PHOTO SLIDESHOW",screen_mirror:"SCREEN MIRROR"};
const videoSources = new Set(["youtube_video","guest_video","guest_audio","guest_photos","screen_mirror"]);
function text(id, value){$(id).textContent=String(value==null?"":value);}
function clear(id){$(id).replaceChildren();}
function tag(name,label,cls){const node=document.createElement(name);if(cls)node.className=cls;node.textContent=label;return node;}
function toast(message){text("toast",message);$("toast").classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>$("toast").classList.remove("show"),3000);}
async function api(path,options){
 const result=await fetch(path,Object.assign({cache:"no-store"},options||{}));
 const type=result.headers.get("Content-Type")||"";
 const data=type.includes("json")?await result.json():{message:await result.text()};
 if(!result.ok || data.success===false)throw new Error(data.error||data.message||"PiRadio request failed");
 return data;
}
function post(path,data){return api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});}
function run(promise){return promise.catch(error=>toast(error.message||"Connection problem"));}
function setTab(tab){
 if(!["home","radio","bible","video","more"].includes(tab))return;
 state.tab=tab;
 document.querySelectorAll("section.view").forEach(el=>el.classList.toggle("active",el.id==="view-"+tab));
 document.querySelectorAll("[data-tab]").forEach(el=>el.classList.toggle("active",el.dataset.tab===tab));
 if(tab==="radio")run(loadRadio());
 if(tab==="bible")run(loadBible());
 if(tab==="more")run(loadWeather());
 if(tab==="video")run(loadVideo());
 window.scrollTo({top:0,behavior:"instant"});
}
document.querySelectorAll("[data-tab]").forEach(b=>b.addEventListener("click",()=>setTab(b.dataset.tab)));
document.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>setTab(b.dataset.go)));
function formatTime(value){
 const seconds=Math.max(0,Math.floor(Number(value)||0));
 return seconds>=3600?Math.floor(seconds/3600)+":"+String(Math.floor(seconds/60)%60).padStart(2,"0")+":"+String(seconds%60).padStart(2,"0"):Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0");
}
async function updateSession(){
 const session=await api("/api/media/session");
 state.session=session;
 $("online-dot").classList.add("ok");
 text("connection","Connected");
 const source=session.source||"radio";
 text("home-source",sources[source]||"NOW PLAYING");
 text("home-title",session.title||"PiRadio");
 const status=session.paused?"PAUSED":session.playing?"PLAYING":"READY";
 text("home-status",status);
 text("home-detail",session.minimized?"Playing in background":"Playback on your Raspberry Pi");
 text("media-toggle",session.playing?"⏸":"▶");
 if(!state.volumeEditing){$("volume-slider").value=String(session.volume||0);}
 text("volume-label",String(session.volume||0)+"%");
 const mpv=videoSources.has(source);
 const canSeek=mpv && !!session.seekable && Number(session.duration)>0;
 $("home-seek-wrap").hidden=!canSeek;
 if(canSeek){
  $("home-seek").max=String(session.duration);
  if(!state.seekEditing)$("home-seek").value=String(Math.max(0,Number(session.position)||0));
  text("home-time",formatTime(session.position)+" / "+formatTime(session.duration));
 }
 $("open-cinema").disabled=!mpv;
 $("media-stop").disabled=!(session.playing||session.paused);
 if(mpv){run(loadVideo());}else{
  state.video=null;$("video-controls").style.display="none";
 }
}
async function transport(action){
 const session=state.session||{};
 const source=session.source||"radio";
 if(source==="bible"){
  await bibleCommand(action==="toggle"?"pause":action);
 }else if(videoSources.has(source)){
  const command=action==="toggle"?"pause":action;
  if((action==="next"||action==="prev") && source!=="guest_photos"){
   const status=state.video||await api("/api/youtube/video/status");
   if(!status.seekable)throw new Error("Timeline unavailable");
   await post("/api/youtube/video",{action:"seek_relative",seconds:action==="next"?10:-10});
  }else{
   await post("/api/youtube/video",{action:command});
  }
 }else{
  await post("/api/remote-v2/transport",{action:action});
 }
 await updateSession();
}
$("media-prev").addEventListener("click",()=>run(transport("prev")));
$("media-toggle").addEventListener("click",()=>run(transport("toggle")));
$("media-next").addEventListener("click",()=>run(transport("next")));
$("media-stop").addEventListener("click",()=>run(transport("stop")));
$("open-cinema").addEventListener("click",()=>setTab("video"));
$("volume-slider").addEventListener("pointerdown",()=>state.volumeEditing=true);
$("volume-slider").addEventListener("input",()=>text("volume-label",$("volume-slider").value+"%"));
$("volume-slider").addEventListener("change",()=>run(api("/api/volume/set/"+Number($("volume-slider").value)).then(()=>{state.volumeEditing=false;})));
$("volume-slider").addEventListener("pointerup",()=>state.volumeEditing=false);
$("home-seek").addEventListener("pointerdown",()=>state.seekEditing=true);
$("home-seek").addEventListener("input",()=>text("home-time",formatTime($("home-seek").value)+" / "+formatTime(state.session&&state.session.duration)));
$("home-seek").addEventListener("change",()=>{
 state.seekEditing=false;run(post("/api/youtube/video",{action:"seek",seconds:Number($("home-seek").value)}).then(updateSession));
});
$("home-seek").addEventListener("pointerup",()=>state.seekEditing=false);

async function loadRadio(){
 const [stations,favorites]=await Promise.all([api("/api/stations"),api("/api/remote-v2/favorites")]);
 state.stations=Array.isArray(stations)?stations:[];
 state.favorites=favorites.indices||[];
 renderRadio();
}
function renderRadio(){
 const q=$("station-filter").value.trim().toLowerCase();
 clear("station-list");clear("favourite-list");
 const stations=state.stations;
 const filtered=stations.map((st,index)=>({st,index})).filter(item=>{
  const name=String(item.st.name||"");
  const genre=String(item.st.genre||"");
  return (name+" "+genre).toLowerCase().includes(q);
 }).slice(0,80);
 for(const item of filtered){
  const row=tag("div","","row");
  const label=tag("div","","grow");
  label.append(tag("strong",item.st.name||"Radio"),tag("small",item.st.genre||"Internet radio"));
  const play=tag("button","▶","small-btn");play.type="button";play.setAttribute("aria-label","Play "+String(item.st.name||"station"));
  play.addEventListener("click",()=>run(api("/api/play/"+item.index).then(updateSession)));
  const fav=tag("button",state.favorites.includes(item.index)?"★":"☆","small-btn");
  fav.type="button";fav.setAttribute("aria-label","Toggle favourite "+String(item.st.name||"station"));
  fav.addEventListener("click",()=>run(post("/api/remote-v2/favorites",{action:"toggle",index:item.index}).then(()=>{
    toast("Favourite update sent");setTimeout(()=>run(loadRadio()),350);
   })));
  row.append(label,fav,play);$("station-list").append(row);
 }
 if(!filtered.length)$("station-list").append(tag("p","No matching stations","muted"));
 text("favourite-count",state.favorites.length+"/6");
 for(const idx of state.favorites){
  const st=stations[idx];
  if(!st)continue;
  const row=tag("div","","row");
  const label=tag("div",st.name||"Radio","grow");
  const play=tag("button","Play","small-btn");
  play.addEventListener("click",()=>run(api("/api/play/"+idx).then(updateSession)));
  row.append(label,play);$("favourite-list").append(row);
 }
 if(!$("favourite-list").children.length)$("favourite-list").append(tag("p","Tap ☆ beside a station to save it.","muted"));
}
$("station-filter").addEventListener("input",renderRadio);
$("radio-refresh").addEventListener("click",()=>run(loadRadio()));

async function loadBible(){
 const data=await api("/api/remote-v2/bible");
 state.bible=data;
 text("bible-current",data.name+" "+data.chapter);
 text("bible-info",data.playing?(data.paused?"Paused":"Playing"):"Saved position");
 const books=$("bible-book"),chapters=$("bible-chapter");
 const previous=books.options.length===data.books.length?Number(books.value):-1;
 if(books.options.length!==data.books.length){
  books.replaceChildren();
  data.books.forEach((b,i)=>{const opt=tag("option",b.name);opt.value=String(i);books.append(opt);});
 }
 if(previous<0)books.value=String(data.book);
 fillChapters(chapters,Number(books.value),data.counts,data.chapter);
 clear("bible-bookmarks");
 (data.bookmarks||[]).forEach(item=>{
  const book=Number(item[0]),chapter=Number(item[1]);
  if(!data.books[book]||chapter<1||chapter>data.counts[book])return;
  const row=tag("div","","row");
  row.append(tag("div",data.books[book].name+" "+chapter,"grow"));
  const btn=tag("button","Play","small-btn");
  btn.addEventListener("click",()=>run(bibleCommand("select",{book:book,chapter:chapter,autoplay:true})));
  row.append(btn);$("bible-bookmarks").append(row);
 });
 if(!$("bible-bookmarks").children.length)$("bible-bookmarks").append(tag("p","No bookmarks saved yet.","muted"));
}
function fillChapters(select,book,counts,selected){
 select.replaceChildren();
 const count=counts[book]||1;
 for(let i=1;i<=count;i++){const opt=tag("option",i);opt.value=String(i);select.append(opt);}
 select.value=String(Math.min(count,Math.max(1,selected||1)));
}
$("bible-book").addEventListener("change",()=>{
 const b=Number($("bible-book").value);
 fillChapters($("bible-chapter"),b,state.bible?state.bible.counts:[],1);
});
async function bibleCommand(action,extra){
 await post("/api/remote-v2/bible",Object.assign({action:action},extra||{}));
 toast("Command sent to PiRadio");
 setTimeout(()=>{run(loadBible());run(updateSession());},650);
}
$("bible-play").addEventListener("click",()=>run(bibleCommand("select",{
 book:Number($("bible-book").value),chapter:Number($("bible-chapter").value),autoplay:true
})));
$("bible-pause").addEventListener("click",()=>run(bibleCommand("pause")));
$("bible-prev").addEventListener("click",()=>run(bibleCommand("prev")));
$("bible-next").addEventListener("click",()=>run(bibleCommand("next")));
$("bible-bookmark").addEventListener("click",()=>run(bibleCommand("bookmark")));

async function searchYouTube(event){
 event.preventDefault();const query=$("youtube-query").value.trim();
 if(!query)return;
 text("youtube-results","Searching…");
 try{
  const result=await post("/api/youtube/search",{query:query});
  clear("youtube-results");
  for(const item of (result.results||[]).slice(0,16)){
   const row=tag("div","","row");
   const label=tag("div","","grow");
   label.append(tag("strong",item.title||"YouTube"),tag("small",item.uploader||""));
   const audio=tag("button","Audio","small-btn");audio.type="button";
   audio.addEventListener("click",()=>run(post("/api/youtube/play",{
    video_id:item.id,title:item.title
   }).then(updateSession)));
   const video=tag("button","Video","small-btn primary");video.type="button";
   video.addEventListener("click",()=>run(post("/api/youtube/video",{
    action:"play",video_id:item.id,title:item.title
   }).then(loadVideo)));
   row.append(label,audio,video);$("youtube-results").append(row);
  }
  if(!$("youtube-results").children.length)text("youtube-results","No results found");
 }catch(error){text("youtube-results",error.message||"Search failed");}
}
$("youtube-form").addEventListener("submit",searchYouTube);
async function videoCommand(action,seconds){
 await post("/api/youtube/video",{action:action,seconds:seconds});
 await loadVideo();
}
async function setCinemaVolume(value){
 const level=Math.max(0,Math.min(100,Math.round(Number(value)||0)));
 const response=await post("/api/youtube/video",{action:"volume",level:level});
 const actual=Number(response.volume);
 const volume=Number.isFinite(actual)?actual:level;
 $("video-volume").value=String(volume);
 text("video-volume-label",volume+"%");
 $("volume-slider").value=String(volume);
 text("volume-label",volume+"%");
 if(state.session)state.session.volume=volume;
}
$("video-volume").addEventListener("pointerdown",()=>state.cinemaVolumeEditing=true);
$("video-volume").addEventListener("input",()=>text("video-volume-label",$("video-volume").value+"%"));
$("video-volume").addEventListener("change",()=>{
 state.cinemaVolumeEditing=false;
 run(setCinemaVolume($("video-volume").value));
});
$("video-volume-up").addEventListener("click",()=>run(setCinemaVolume(Number($("video-volume").value)+5)));
$("video-volume-down").addEventListener("click",()=>run(setCinemaVolume(Number($("video-volume").value)-5)));
async function loadVideo(){
 if(state.tab!=="video" && !(state.session&&videoSources.has(state.session.source)))return;
 const data=await api("/api/youtube/video/status");
 state.video=data;
 $("video-controls").style.display=data.playing?"block":"none";
 if(!data.playing)return;
 text("video-source",sources[data.source]||"PI CINEMA");
 text("video-title",data.title||"PiRadio media");
 text("video-state",data.paused?"Paused":data.buffering?"Buffering…":data.minimized?"Playing in background":"Playing on Pi");
 text("video-time",data.seekable?formatTime(data.position)+" / "+formatTime(data.duration):"Live / No seek");
 if(!state.cinemaVolumeEditing && Number.isFinite(Number(data.volume))){
  const level=Math.max(0,Math.min(100,Math.round(Number(data.volume))));
  $("video-volume").value=String(level);
  text("video-volume-label",level+"%");
 }
 const photo=data.source==="guest_photos",seekable=!!data.seekable;
 const prev=$("video-prev"),next=$("video-next");
 prev.textContent=photo?"Previous photo":"-10s";
 next.textContent=photo?"Next photo":"+10s";
 prev.disabled=next.disabled=!(photo||seekable);
 $("video-toggle").textContent=data.paused?"Play":"Pause";
 const video=data.source==="youtube_video"||data.source==="guest_video"||data.source==="screen_mirror";
 $("video-minimize").disabled=!video||!!data.minimized;
 $("video-restore").disabled=!video||!data.minimized;
 $("video-seek").disabled=!seekable;
 $("video-seek").max=String(Math.max(1,Number(data.duration)||1));
 if(!state.videoEditing)$("video-seek").value=String(Number(data.position)||0);
}
$("video-prev").addEventListener("click",()=>run(
 state.video&&state.video.source==="guest_photos"?
 videoCommand("prev"):videoCommand("seek_relative",-10)));
$("video-next").addEventListener("click",()=>run(
 state.video&&state.video.source==="guest_photos"?
 videoCommand("next"):videoCommand("seek_relative",10)));
$("video-toggle").addEventListener("click",()=>run(videoCommand("pause")));
$("video-minimize").addEventListener("click",()=>run(videoCommand("minimize")));
$("video-restore").addEventListener("click",()=>run(videoCommand("restore")));
$("video-stop").addEventListener("click",()=>run(videoCommand("stop")));
$("video-seek").addEventListener("pointerdown",()=>state.videoEditing=true);
$("video-seek").addEventListener("change",()=>{state.videoEditing=false;run(videoCommand("seek",Number($("video-seek").value)));});
$("video-seek").addEventListener("pointerup",()=>state.videoEditing=false);

async function loadWeather(){
 const data=await api("/api/weather/current");
 text("weather-city",data.city||"Selected location");
 text("weather-temperature",data.available && Number.isFinite(Number(data.temp))?Math.round(Number(data.temp))+"°":"--°");
 text("weather-condition",data.available?String(data.condition||"Current conditions").replaceAll("_"," "):"Weather currently unavailable");
 clear("weather-forecast");
 for(const day of (data.forecast||[]).slice(0,5)){
  const block=tag("div",String(day.day||day.date||"--"));
  block.append(tag("div",String(day.high==null?"--":day.high)+"° / "+String(day.low==null?"--":day.low)+"°"));
  $("weather-forecast").append(block);
 }
}
$("weather-refresh").addEventListener("click",()=>run(post("/api/weather/refresh",{}).then(()=>{toast("Refresh requested");return loadWeather();})));
document.querySelectorAll("[data-sleep]").forEach(b=>b.addEventListener("click",()=>run(post("/api/sleep/start",{minutes:Number(b.dataset.sleep)}).then(()=>toast("Sleep timer set")))));
$("sleep-cancel").addEventListener("click",()=>run(post("/api/sleep/cancel",{}).then(()=>toast("Sleep timer cancelled"))));

async function poll(){
 if(state.pollBusy || document.hidden)return;
 state.pollBusy=true;
 try{
  await updateSession();
  if(state.tab==="more")await loadWeather();
  $("online-dot").classList.add("ok");text("connection","Connected");
 }catch(error){
  $("online-dot").classList.remove("ok");text("connection","Offline");
 }finally{state.pollBusy=false;}
}
poll();
setInterval(poll,3000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)poll();});
</script>
</body>
</html>
"""
