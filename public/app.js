const $ = s => document.querySelector(s);
let state = {stylists:[],chairs:[],appointments:[],clients:[]}, selectedDate = new Date(), mode='day', view='calendar', busy=false;
const form=$('#appointment-form'), dialog=$('#appointment-dialog');
let calendarFocusKey = null;
const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const formatTime = d => new Date(d).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
const stylist = id => state.stylists.find(s=>s.id===Number(id));
const localDay = value => dateKey(new Date(value));
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,3000)}
async function api(path, method='GET', data){const response=await fetch(path,{method,headers: data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});const result=await response.json();if(!response.ok)throw new Error(result.error||'Unable to save changes.');return result}
async function refresh(){try{const next=await api('/api/state');if(state.revision&&next.revision&&state.revision!==next.revision){location.reload();return}state=next;$('#global-error').hidden=true;$('#sync-status').textContent='Updated '+formatTime(new Date());render()}catch(e){$('#global-error').textContent='Unable to connect to the shared calendar. Check that the server is running. Your changes have not been saved.';$('#global-error').hidden=false;$('#sync-status').textContent='Connection unavailable'}}
function render(){
 const filter=$('#stylist-filter'), previous=filter.value;filter.innerHTML='<option value="">All stylists</option>'+state.stylists.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');filter.value=previous;
 const todays=state.appointments.filter(a=>localDay(a.start)===dateKey(new Date())&&a.status!=='cancelled');
 const scheduled=state.appointments.filter(a=>a.status==='confirmed'&&new Date(a.start)>new Date());
 const occupied=state.chairs.filter(c=>c.stylist_id).length;
 const pending=scheduled.filter(a=>a.reminder&&a.email&&!a.reminder_sent).length;
 $('#stats').innerHTML=[['Appointments today',todays.length,'Across the whole salon','▦'],['Chairs rented',`${occupied} <span style="font-size:17px;color:#a58a94">/ ${state.chairs.length}</span>`,`${state.chairs.length-occupied} available for your team`,'◫'],['Your team',state.stylists.length,'Stylists sharing this space','♧'],['Reminder queue',pending,state.email_configured?'Email delivery is configured':'Email setup needed','✉']].map(([label,value,detail,icon])=>`<div class="stat"><span class="stat-icon">${icon}</span><div class="stat-label">${label}</div><div class="stat-value">${value}</div><div class="stat-detail">${detail}</div></div>`).join('');
 renderCalendar();renderChairs();renderReminders();renderClients();
}
function weekStart(){let d=new Date(selectedDate);d.setDate(d.getDate()-((d.getDay()+6)%7));return d}
function renderCalendar(){
 const previousScroll={top:$('#calendar').scrollTop,left:$('#calendar').scrollLeft};
 const filter=$('#stylist-filter').value, people=state.stylists.filter(s=>!filter||s.id===Number(filter));
 let columns=[];
 if(mode==='day'){columns=people.map(s=>({date:new Date(selectedDate),stylist:s,label:s.name,sub:state.chairs.filter(c=>c.stylist_id===s.id).map(c=>c.name).join(', ')||'No chair assigned'}));$('#period-label').textContent=selectedDate.toLocaleDateString([],{month:'long',day:'numeric',year:'numeric'})}
 else{const start=weekStart();columns=Array.from({length:7},(_,i)=>{let d=new Date(start);d.setDate(d.getDate()+i);return {date:d,label:d.toLocaleDateString([],{weekday:'short',day:'numeric'}),sub:filter?stylist(filter)?.name:'All stylists'}});$('#period-label').textContent=start.toLocaleDateString([],{month:'short',day:'numeric'})+' – '+columns[6].date.toLocaleDateString([],{month:'short',day:'numeric'})}
 $('#day-mode').classList.toggle('selected',mode==='day');$('#week-mode').classList.toggle('selected',mode==='week');
 // Expand displayed hours for early or late appointments, including bookings crossing midnight.
 const dates=columns.map(c=>dateKey(c.date));
 const appointments=state.appointments.filter(a=>(!filter||a.stylist_id===Number(filter))&&dates.some(key=>overlapsDay(a,key)));
 const now=new Date(), todayKey=dateKey(now), showsToday=dates.includes(todayKey);
 let minHour=8,maxHour=21;
 if(showsToday){minHour=Math.min(minHour,now.getHours());maxHour=Math.max(maxHour,now.getHours()+1)}
 appointments.forEach(a=>{const d=new Date(a.start),end=new Date(d.getTime()+a.duration*60000);if(dateKey(d)!==dateKey(end)){minHour=0;maxHour=24}minHour=Math.min(minHour,dates.includes(dateKey(d))?d.getHours():0);maxHour=Math.max(maxHour,dates.includes(dateKey(end))?Math.ceil(end.getHours()+end.getMinutes()/60):24)});
 const height=(maxHour-minHour)*60;
 const nowY=(now.getHours()*60+now.getMinutes()+now.getSeconds()/60)-minHour*60;
 const nowLabel=esc(formatTime(now));
 const headers='<div class="column-heading"></div>'+columns.map(c=>`<div class="column-heading">${c.stylist?`<span class="color-dot" style="background:${c.stylist.color}"></span>`:''}${esc(c.label)}<small>${esc(c.sub)}</small></div>`).join('');
 const hours=Array.from({length:maxHour-minHour},(_,i)=>minHour+i);
 const times=`<div class="time-column" style="height:${height}px">${showsToday?`<span class="current-time-label" style="top:${nowY}px" aria-label="Current time ${nowLabel}">${nowLabel}</span>`:''}${hours.map(h=>`<span class="time-label" style="top:${(h-minHour)*60+10}px;${showsToday&&Math.abs((h-minHour)*60+10-nowY)<18?'visibility:hidden':''}">${h%12||12} ${h<12?'AM':'PM'}</span>`).join('')}</div>`;
 let cells=columns.map((c,index)=>{
  let bookings=appointments.filter(a=>overlapsDay(a,dateKey(c.date))&&(!c.stylist||a.stylist_id===c.stylist.id));
  const positioned=bookings.map(a=>{const start=new Date(a.start),end=new Date(start.getTime()+a.duration*60000),begin=new Date(c.date);begin.setHours(0,0,0,0);const next=new Date(begin);next.setDate(next.getDate()+1);return {a,top:Math.max(0,(Math.max(start,begin)-begin)/60000-minHour*60),bottom:Math.min(height,(Math.min(end,next)-begin)/60000-minHour*60)}}).sort((a,b)=>a.top-b.top);
  // Side-by-side lanes keep concurrent stylists visible in the week view.
  let groups=[],group=[],end=-1;for(const b of positioned){if(b.top>=end){if(group.length)groups.push(group);group=[];end=-1}group.push(b);end=Math.max(end,b.bottom)}if(group.length)groups.push(group);
  let cards='';for(const group of groups){let lanes=[];for(const b of group){let lane=lanes.findIndex(end=>end<=b.top);if(lane<0)lane=lanes.length;lanes[lane]=b.bottom;b.lane=lane}for(const b of group){const a=b.a,s=stylist(a.stylist_id);cards+=`<button class="booking ${esc(a.status)}" data-id="${a.id}" style="--booking-color:${s?.color||'#79834c'};top:${b.top}px;height:${Math.max(24,b.bottom-b.top-3)}px;left:calc(${b.lane*100/lanes.length}% + 4px);width:calc(${100/lanes.length}% - 8px)" aria-label="Edit ${esc(a.client)}, ${esc(a.service)}, ${esc(formatTime(a.start))}"><strong>${esc(a.client)}</strong><small>${esc(a.service)}</small><small>${esc(formatTime(a.start))} · ${a.duration} min</small>${mode==='week'?`<small>${esc(s?.name)}</small>`:''}${a.status!=='confirmed'?`<small>${esc(a.status)}</small>`:''}</button>`}}
  return `<div class="day-column" data-date="${dateKey(c.date)}" style="height:${height}px">${hours.map(h=>`<button class="slot" data-col="${index}" data-hour="${h}" style="top:${(h-minHour)*60}px" aria-label="New appointment ${esc(c.label)} at ${h}:00"></button>`).join('')}${cards}${dateKey(c.date)===todayKey?`<div class="current-time-line" style="top:${nowY}px" aria-hidden="true"></div>`:''}</div>`;
 }).join('');
 $('#calendar').innerHTML=`<div class="schedule" style="--cols:${columns.length}">${headers}${times}${cells}</div>`+(!appointments.length?'<div class="empty-note">A fresh page. Add your first appointment with the button above or click a time on the calendar.</div>':'');
 $('#calendar').scrollTop=previousScroll.top;$('#calendar').scrollLeft=previousScroll.left;
 const focusKey=mode+':'+dateKey(selectedDate)+':'+filter;
 if(view==='calendar'&&calendarFocusKey!==focusKey){
  calendarFocusKey=focusKey;
  if(showsToday){
   const calendar=$('#calendar'), column=calendar.querySelector(`[data-date="${todayKey}"]`), header=calendar.querySelector('.column-heading');
   const headerHeight=header?.offsetHeight||0;
   calendar.scrollTop=Math.max(0,column.offsetTop+nowY-headerHeight-(calendar.clientHeight-headerHeight)*0.35);
   if(mode==='week')calendar.scrollLeft=Math.max(0,column.offsetLeft-65);
   column.querySelector('.current-time-line')?.scrollIntoView({block:'center',inline:'nearest'});
  }else{$('#calendar').scrollTop=0;$('#calendar').scrollLeft=0}
 }
 $('#booking-count').textContent=`${appointments.length} appointment${appointments.length===1?'':'s'} shown`;
 $('#calendar').querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>openAppointment(Number(b.dataset.id)));
 $('#calendar').querySelectorAll('[data-hour]').forEach(b=>b.onclick=()=>{let c=columns[Number(b.dataset.col)];openAppointment(null,c.date,Number(b.dataset.hour),c.stylist?.id||Number(filter)||undefined)});
}
function overlapsDay(a,key){const day=new Date(key+'T00:00:00'),end=new Date(day);end.setDate(end.getDate()+1);return new Date(a.start)<end&&new Date(new Date(a.start).getTime()+a.duration*60000)>day}
function renderChairs(){
 $('#chair-grid').innerHTML=state.chairs.map(c=>`<article class="chair-card"><span class="badge">${c.stylist_id?'Rented':'Available'}</span><div class="chair-symbol">◫</div><h2>${esc(c.name)}</h2><p>${c.stylist_id?esc(stylist(c.stylist_id)?.name)+'’s space to create.':'Ready for someone new.'}</p><label>Rented by<select data-chair="${c.id}"><option value="">Available · unassigned</option>${state.stylists.map(s=>`<option value="${s.id}" ${c.stylist_id===s.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label></article>`).join('');
 $('#chair-grid').querySelectorAll('select').forEach(s=>s.onchange=async()=>{s.disabled=true;try{await api('/api/chairs/'+s.dataset.chair,'PUT',{stylist_id:Number(s.value)||null});await refresh();toast('Chair assignment updated')}catch(e){toast(e.message);await refresh()}});
 $('#team-list').innerHTML=state.stylists.map(s=>`<button class="team-member" data-stylist="${s.id}" aria-label="Rename ${esc(s.name)}"><span class="team-avatar" style="background:${s.color}">${esc(s.name.split(' ').map(n=>n[0]).slice(0,2).join(''))}</span>${esc(s.name)} <small>✎</small></button>`).join('');
 $('#team-list').querySelectorAll('[data-stylist]').forEach(b=>b.onclick=()=>openTeam(Number(b.dataset.stylist)));
}
function renderReminders(){
 $('#email-status').textContent=state.email_configured?'Email reminders are enabled. The server checks every minute for confirmed appointments due within three days.':'Email delivery is not connected yet. You can queue reminders now; add SMTP settings to the server to enable automatic delivery.';
 const rows=state.appointments.filter(a=>a.reminder&&a.email&&a.status==='confirmed'&&new Date(a.start)>new Date()).sort((a,b)=>new Date(a.start)-new Date(b.start));
 $('#reminder-list').innerHTML=rows.length?rows.map(a=>`<div class="reminder-row"><button data-id="${a.id}"><strong>${esc(a.client)}</strong><small>${esc(a.service)} · ${new Date(a.start).toLocaleDateString()} at ${esc(formatTime(a.start))}</small><small>${esc(a.email)}</small></button><span class="badge">${a.reminder_sent?'Sent':state.email_configured?'Queued':'Needs email setup'}</span></div>`).join(''):'<div class="empty-note">No upcoming reminders. Add an email address and enable the reminder on an appointment.</div>';
 $('#reminder-list').querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>openAppointment(Number(b.dataset.id)));
}
function openAppointment(id,date=selectedDate,hour=9,stylistId){
 form.reset();$('#form-error').textContent='';const a=state.appointments.find(a=>a.id===id), f=form.elements;
 f.stylist_id.innerHTML=state.stylists.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');f.chair_id.innerHTML=state.chairs.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('');
 f.client_id.innerHTML='<option value="">New client · enter details below</option>'+[...(state.clients||[])].sort((a,b)=>a.name.localeCompare(b.name)).map(c=>`<option value="${c.id}">${esc(c.name)}${c.email?' · '+esc(c.email):c.phone?' · '+esc(c.phone):''}${c.active?'':' · inactive'} · #${c.id}</option>`).join('');
 f.id.value=id||'';$('#dialog-title').textContent=id?'Edit appointment':'New appointment';
 if(a){f.client_id.value=a.client_id||'';for(const key of ['client','email','phone','service','stylist_id','chair_id','notes','status'])f[key].value=a[key];if(![...f.duration.options].some(o=>Number(o.value)===a.duration))f.duration.add(new Option(`${a.duration} minutes`,a.duration));f.duration.value=a.duration;const d=new Date(a.start);f.date.value=dateKey(d);f.time.value=String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');f.reminder.checked=!!a.reminder}
 else{f.date.value=dateKey(date);f.time.value=String(hour).padStart(2,'0')+':00';f.stylist_id.value=stylistId||state.stylists[0]?.id;assignChair()}
 $('#reminder-hint').textContent=state.email_configured?'An email address is needed. Reminders send automatically while the server is running.':'Email delivery needs server setup. Your reminder preference will be saved.';dialog.showModal();
}
function assignChair(){const chair=state.chairs.find(c=>c.stylist_id===Number(form.elements.stylist_id.value));if(chair)form.elements.chair_id.value=chair.id}
form.elements.stylist_id.onchange=assignChair;
form.onsubmit=async event=>{event.preventDefault();if(busy)return;busy=true;$('#save-button').disabled=true;$('#form-error').textContent='';try{let data=Object.fromEntries(new FormData(form));if(data.reminder&&!data.email)throw new Error('Add an email address to enable a reminder.');data.start=new Date(data.date+'T'+data.time).toISOString();data.reminder=form.elements.reminder.checked;await api('/api/appointments'+(data.id?'/'+data.id:''),data.id?'PUT':'POST',data);dialog.close();await refresh();toast('Appointment saved')}catch(e){$('#form-error').textContent=e.message}finally{busy=false;$('#save-button').disabled=false}};
$('#close-dialog').onclick=$('#cancel-dialog').onclick=()=>dialog.close();$('#new-appointment').onclick=()=>openAppointment();
$('#prev').onclick=()=>{selectedDate.setDate(selectedDate.getDate()-(mode==='day'?1:7));renderCalendar()};$('#next').onclick=()=>{selectedDate.setDate(selectedDate.getDate()+(mode==='day'?1:7));renderCalendar()};$('#today').onclick=()=>{selectedDate=new Date();calendarFocusKey=null;renderCalendar()};$('#day-mode').onclick=()=>{mode='day';renderCalendar()};$('#week-mode').onclick=()=>{mode='week';renderCalendar()};$('#stylist-filter').onchange=renderCalendar;
const titles={clients:['Your clients, all in one place.','Keep contact details and service history connected.'],calendar:['Your day, beautifully planned.','Make room for great hair. We’ll keep track of the rest.'],chairs:['Good people. Beautiful spaces.','A simple overview of your chairs and the people behind them.'],reminders:['One less thing to remember.','Help your clients arrive ready for a little time for themselves.']};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;if(view==='calendar')calendarFocusKey=null;document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n===b));for(const name of Object.keys(titles))$('#'+name+'-view').hidden=name!==view;$('#page-title').textContent=titles[view][0];$('#page-subtitle').textContent=titles[view][1];$('#page-crumb').textContent=view==='chairs'?'CHAIRS & TEAM':view.toUpperCase();if(view==='calendar')renderCalendar();if(view==='clients')renderClients()});
function openTeam(id){const f=$('#team-form');f.reset();f.elements.id.value=id||'';if(id)f.elements.name.value=stylist(id).name;$('#team-dialog-title').textContent=id?'Rename stylist':'Add a stylist';f.querySelector('[type=submit]').textContent=id?'Save name':'Add to team';$('#team-error').textContent='';$('#team-dialog').showModal()}
$('#add-stylist').onclick=()=>openTeam();$('#close-team').onclick=()=>$('#team-dialog').close();
$('#team-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;try{const id=e.target.elements.id.value;await api('/api/team'+(id?'/'+id:''),id?'PUT':'POST',{name:e.target.elements.name.value});$('#team-dialog').close();await refresh();toast('Team updated')}catch(error){$('#team-error').textContent=error.message}finally{button.disabled=false}};
$('#today-label').textContent=new Date().toLocaleDateString([],{weekday:'long',month:'short',day:'numeric'});
refresh();setInterval(()=>{if(!document.hidden&&!dialog.open&&!$('#team-dialog').open&&!$('#client-dialog').open&&!busy)refresh()},15000);

// Keep the time marker moving even when shared-calendar refresh is unavailable.
setInterval(()=>{if(!document.hidden&&view==='calendar'&&!dialog.open&&!busy)renderCalendar()},60000);

const clientForm=$('#client-form'), clientDialog=$('#client-dialog');
const clientBookings=id=>state.appointments.filter(a=>a.client_id===id).sort((a,b)=>new Date(b.start)-new Date(a.start));
const pastServices=id=>clientBookings(id).filter(a=>a.status==='completed'||(a.status==='confirmed'&&new Date(new Date(a.start).getTime()+a.duration*60000)<=new Date()));
function renderClients(){
 const query=$('#client-search').value.trim().toLowerCase(),activeOnly=$('#active-clients-only').checked;
 const clients=(state.clients||[]).filter(c=>(!activeOnly||c.active)&&(!query||[c.name,c.email,c.phone].some(v=>v.toLowerCase().includes(query)))).sort((a,b)=>a.name.localeCompare(b.name));
 $('#client-count').textContent=clients.length+' client'+(clients.length===1?'':'s')+' shown';
 $('#client-list').innerHTML=clients.length?clients.map(c=>{const history=pastServices(c.id),last=history[0];return `<article class="client-row"><button type="button" class="client-summary" data-client="${c.id}"><span class="client-avatar">${esc(c.name.split(/\s+/).map(n=>n[0]).slice(0,2).join(''))}</span><span><strong>${esc(c.name)}</strong><small>${esc([c.email,c.phone].filter(Boolean).join(' · ')||'No contact details yet')}</small><small>${history.length} past service${history.length===1?'':'s'}${last?' · Last: '+esc(last.service)+' · '+new Date(last.start).toLocaleDateString():''}</small></span><span class="client-open">View profile ↗</span></button><label class="check-label client-active"><input type="checkbox" data-client-active="${c.id}" ${c.active?'checked':''}> Active</label></article>`}).join(''):'<div class="empty-note">'+(query?'No matching clients. Try another search.':activeOnly?'No active clients to show. Add a client or uncheck the active filter.':'No clients yet. Add your first client or save an appointment to create a record.')+'</div>';
 $('#client-list').querySelectorAll('[data-client]').forEach(b=>b.onclick=()=>openClient(Number(b.dataset.client)));
 $('#client-list').querySelectorAll('[data-client-active]').forEach(input=>input.onchange=async()=>{const c=state.clients.find(c=>c.id===Number(input.dataset.clientActive));input.disabled=true;try{await api('/api/clients/'+c.id,'PUT',{...c,active:input.checked});await refresh();toast('Client status saved')}catch(e){input.checked=!!c.active;input.disabled=false;toast(e.message)}});
}
function openClient(id){
 clientForm.reset();$('#client-error').textContent='';const c=(state.clients||[]).find(c=>c.id===id),f=clientForm.elements;f.id.value=id||'';
 $('#client-dialog-title').textContent=c?c.name:'New client';
 if(c){for(const key of ['name','email','phone','notes'])f[key].value=c[key];f.active.checked=!!c.active}
 $('#client-history-panel').hidden=!c;
 if(c){const bookings=clientBookings(id),past=bookings.filter(a=>new Date(a.start)<=new Date()||a.status!=='confirmed'),upcoming=bookings.filter(a=>new Date(a.start)>new Date()&&a.status==='confirmed').reverse();
 const rows=items=>items.map(a=>`<button class="client-history-row" type="button" data-history-id="${a.id}"><span><strong>${esc(a.service)}</strong><small>${new Date(a.start).toLocaleDateString()} · ${esc(formatTime(a.start))} · ${a.duration} min · ${esc(stylist(a.stylist_id)?.name||'Stylist')}</small>${a.notes?`<small class="history-notes">${esc(a.notes)}</small>`:''}</span><span class="badge">${esc(a.status==='confirmed'&&new Date(a.start)<=new Date()?(new Date(new Date(a.start).getTime()+a.duration*60000)>new Date()?'In progress':'Past · confirmed'):a.status)}</span></button>`).join('');
 $('#client-history').innerHTML=(upcoming.length?'<h3>Upcoming appointments</h3>'+rows(upcoming):'')+'<h3>Past services & appointments</h3>'+(past.length?rows(past):'<p class="muted">No past services recorded yet.</p>');
 $('#client-history').querySelectorAll('[data-history-id]').forEach(b=>b.onclick=()=>{clientDialog.close();openAppointment(Number(b.dataset.historyId))});
 }
 clientDialog.showModal();
}
function fillAppointmentClient(id){const c=state.clients.find(c=>c.id===Number(id));if(!c)return;const f=form.elements;f.client_id.value=c.id;f.client.value=c.name;f.email.value=c.email;f.phone.value=c.phone}
form.elements.client_id.onchange=()=>fillAppointmentClient(form.elements.client_id.value);
form.elements.client.oninput=()=>{form.elements.client_id.value=''};
$('#add-client').onclick=()=>openClient();$('#client-search').oninput=renderClients;$('#active-clients-only').onchange=renderClients;
$('#close-client').onclick=$('#cancel-client').onclick=()=>clientDialog.close();
$('#client-new-appointment').onclick=()=>{const id=clientForm.elements.id.value;clientDialog.close();openAppointment();fillAppointmentClient(id)};
clientForm.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;$('#save-client').disabled=true;$('#client-error').textContent='';try{const data=Object.fromEntries(new FormData(clientForm));data.active=clientForm.elements.active.checked;await api('/api/clients'+(data.id?'/'+data.id:''),data.id?'PUT':'POST',data);clientDialog.close();await refresh();toast('Client saved')}catch(error){$('#client-error').textContent=error.message}finally{busy=false;$('#save-client').disabled=false}};
