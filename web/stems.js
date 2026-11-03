/* Optional local processing. Each request uses the existing same-origin token. */
(()=>{
 let selected=null,timer=null,last=null;
 const get=id=>document.getElementById(id);
 async function command(op,value={}){return api('/api/stems/'+op,{method:'POST',headers:{'X-Machinista-Token':token,'Content-Type':'application/json'},body:JSON.stringify(value)})}
 async function refresh(){
  try{
   const s=await api('/api/stems');last=s;
   get('stems-setup').hidden=s.ready;get('stems-install').disabled=s.busy;
   get('stems-start').disabled=s.busy||!s.ready||!selected;
   get('stems-cancel').hidden=!s.busy;get('stems-progress').hidden=!s.busy;
   if(s.busy&&s.progress>0){get('stems-progress').max=100;get('stems-progress').value=s.progress}else get('stems-progress').removeAttribute('value');
   get('stems-status').textContent=s.message||'';
   get('stems-result').hidden=!(s.state==='DONE'&&s.folder);
   if(s.state==='ERROR')get('stems-error').textContent=s.message;
   if(s.busy&&!timer)timer=setInterval(refresh,1500);
   if(!s.busy&&timer){clearInterval(timer);timer=null}
  }catch(e){get('stems-error').textContent=e.message;if(timer){clearInterval(timer);timer=null}}
 }
 window.openStemSeparation=async ref=>{selected={...ref};get('stems-source').textContent=ref.name;get('stems-error').textContent='';get('stems-dialog').showModal();await refresh()};
 for(const [id,op] of [['stems-start','start'],['stems-install','install'],['stems-cancel','cancel']])get(id).onclick=async()=>{
  get(id).disabled=true;get('stems-error').textContent='';try{await command(op,op==='start'?selected:{});await refresh()}catch(e){get('stems-error').textContent=e.message}finally{await refresh()}
 };
 get('stems-result').onclick=()=>{if(!last?.folder)return;source=last.source;path=last.folder;get('source').value=source;get('stems-dialog').close();load()};
 get('stems-close').onclick=()=>get('stems-dialog').close();
 get('stems-dialog').addEventListener('close',()=>{if(timer){clearInterval(timer);timer=null}});
})();
