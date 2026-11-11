"""MK3 dedicated controls share the proven eight-knob engine bindings."""
import copy
from app.mk2_surface import Mk2Surface,Field
from app.controller_settings import on_controller

class Mk3Surface(Mk2Surface):
    source='mk3'
    event_select_button='DISPLAY 4'
    event_select_index=3
    def __init__(self,*args):
        super().__init__(*args);self.strip_mode=None;self.strip_value=0;self.touched=set();self.cursors={};self.cursor_buttons=set()
    def move_cursor(self,step):
        cell=self.cursor_cell()
        if cell is not None:
            beyond=[c for c in self.populated() if (c-cell)*step>0]
            if beyond:self.cursors[self.cursor_key()]=beyond[0] if step>0 else beyond[-1];return
        path=self.channel_page_path()
        bound=max(1,min(32,len(path) if path else self.page_state()[1]))
        seen={self.cursor_key()}
        for _ in range(bound):
            self.change_page(step);key=self.cursor_key()
            if key in seen:return
            seen.add(key)
            cells=self.populated() if self.cursor_active() else []
            if cells:self.cursors[key]=cells[0] if step>0 else cells[-1];return
    @on_controller('mk3')
    def button(self,name,pressed):
        import time
        a=self.app
        if pressed and time.monotonic()<getattr(a,'update_lock_until',0):return
        if a.page=='CLIP ARRANGER' and name in ('MASTER UP','MASTER DOWN','MASTER LEFT','MASTER RIGHT'):
            if pressed:
                if name in self.held:return
                self.held.add(name)
                if name in ('MASTER UP','MASTER DOWN'):a.arranger_rotate(0,-1 if name=='MASTER UP' else 1)
                else:
                    from app.clip_arranger import MAX_TICKS
                    a.arranger_follow=False;a.arranger_cursor=max(0,min(MAX_TICKS-1,a.arranger_cursor+(-1 if name=='MASTER LEFT' else 1)*a.arranger_grid));a.arranger_id=None;a.arranger_sync_selection();a.arranger_ensure_view()
            else:self.held.discard(name)
            return
        if name=='EVENTS':
            if pressed:
                if name in self.held:return
                origin=a.page
                if origin=='LIVE FX':
                    a.live_fx_off()
                    # The FX workspace consumes unknown buttons. Leave it before
                    # dispatching the shared held mode, then retain its return view.
                    a.page=a.control_home()
                    if self.strip_mode=='PERFORM':self.strip_mode=None
                was_editor=a.page in ('PATTERN GRID','GRID EDIT')
                # Both editor pages belong to the same temporary mode.
                if a.page=='GRID EDIT':a.page='PATTERN GRID'
                super().button(name,True)
                if not was_editor and a.page=='PATTERN GRID':
                    a.open_pattern_grid()
                    if origin=='LIVE FX':a.mode_origins['EVENTS']=origin
            else:super().button(name,False)
            return
        if name=='FOLLOW':
            if pressed and name not in self.held and not getattr(self,'follow_grid',False):
                self.follow_grid=a.shift
            if getattr(self,'follow_grid',False):
                if pressed and 'GRID' not in self.held:a.grid_tab=2;a.grid_field=0
                shifted=a.shift;a.shift=False
                try:return super().button('GRID',pressed)
                finally:
                    a.shift=shifted
                    if not pressed:self.follow_grid=False
        if name=='TAP':
            if pressed:
                if name in self.held:return
                self.held.add(name);self.tap_binding='METRONOME' if a.shift else 'TAP'
                if self.tap_binding=='METRONOME':a.timing_button('PLAY',True)
                else:self.inputs.button(self.source,'TAP',True)
            else:
                if name not in self.held:return
                self.held.discard(name)
                if getattr(self,'tap_binding',None)=='TAP':self.inputs.button(self.source,'TAP',False)
                self.tap_binding=None
            return
        if name in ('MASTER LEFT','MASTER RIGHT'):
            # Route each release to the handler that took the press.
            if pressed:
                if not a.shift and self.cursor_active() and (self.cursor_cell() is not None or a.page not in ('SAMPLER','PLUGIN','AUDIO LOOP')):
                    if name in self.held:return
                    self.held.add(name);self.cursor_buttons.add(name);self.move_cursor(-1 if name=='MASTER LEFT' else 1)
                    return
            elif name in self.cursor_buttons:
                self.cursor_buttons.discard(name);self.held.discard(name);return
        if name in ('MASTER LEFT','MASTER RIGHT','MASTER UP','MASTER DOWN') and a.page in ('SAMPLER','PLUGIN','AUDIO LOOP'):
            if pressed:
                if name in self.held:return
                self.held.add(name)
                offset=int(a.sampler_slot_present());count=len(a.plugin_target().get('plugins',[]))+offset
                current=0 if a.page in ('SAMPLER','AUDIO LOOP') else a.plugin_slot+offset
                delta=-1 if name in ('MASTER LEFT','MASTER UP') else 1
                target=max(0,min(count-1,current+delta))
                if count and target!=current:
                    a.parameter_kind='PLUG-IN';a.parameter_choice=target
                    a.plugin_param=0;a.page=a.parameter_destination();a.remember_control_view()
                    self.chain_motion=(getattr(self,'chain_motion',(0,''))[0]+1,name)
            else:self.held.discard(name)
            return
        if name.endswith(' TOUCH'):
            if pressed:self.touched.add(name)
            else:self.touched.discard(name)
            return
        if name in ('LOCK','CHANNEL','PLUG-IN','MIXER','ARRANGER','SETTINGS','FILE','KEYBOARD','CHORDS','FIXED VEL','PERFORM','MACRO','FOLLOW','STOP','PITCH','MOD','NOTES','MASTER UP','MASTER DOWN'):
            if pressed:
                if name in self.held:return
                self.held.add(name)
            else:self.held.discard(name);return
            self.master_mode=None
            if a.page=='LIVE FX' and (name in ('CHANNEL','PLUG-IN','MIXER','ARRANGER','SETTINGS','KEYBOARD','CHORDS','EVENTS','MACRO') or name=='FILE' and not a.shift):
                # Clear owners and record the OFF state before leaving, without
                # restoring an origin that could invert a workspace toggle.
                a.live_fx_off()
                if self.strip_mode=='PERFORM':self.strip_mode=None
            if name=='LOCK':self.lock_parameters()
            elif name in ('CHANNEL','PLUG-IN'):self.property('CHNL' if name=='CHANNEL' else 'PLUG-IN')
            elif name=='MIXER':a.page=a.control_home() if a.page=='MIXER' else 'MIXER'
            elif name=='ARRANGER':
                if a.page in ('SONG','CLIP ARRANGER','CLIP MENU'):a.page=a.control_home()
                elif a.project.get('arrangement',{}).get('mode')=='CLIPS':a.arranger_open()
                else:a.page='SONG'
            elif name=='SETTINGS':
                if a.page=='SETTINGS':a.page=a.control_home()
                else:a.open_settings()
            elif name=='FILE':a.save() if a.shift else setattr(a,'page','PROJECT')
            elif name=='KEYBOARD':
                a.keyboard_enabled=not a.keyboard_enabled;a.velocities16=False
                a.page='PAD CONFIG' if a.keyboard_enabled else a.control_home()
            elif name=='CHORDS':
                a.remember();a.keyboard_enabled=True;a.velocities16=False
                p=a.performance();p['chord_mode']='OFF' if a.keyboard_chord_mode()!='OFF' else 'CUSTOM'
                a.page='PAD CONFIG';self.pad_page=0
            elif name=='FIXED VEL':a.fixed_velocity=not a.fixed_velocity
            elif name=='PERFORM':
                if a.page=='LIVE FX':
                    a.close_live_fx();self.strip_mode=None
                else:
                    self.strip_mode='PERFORM';a.open_live_fx()
            elif name=='MACRO':a.page=a.control_home() if a.page=='MACRO' else 'MACRO'
            elif name=='FOLLOW':
                if a.page in ('PATTERN GRID','GRID EDIT'):a.grid_follow=not a.grid_follow
                else:a.follow=not a.follow
            elif name=='STOP':
                if a.playing:self.tap('PLAY')
            elif name in ('PITCH','MOD','NOTES'):
                if self.strip_value:self.strip(0)
                self.strip_mode=None if self.strip_mode==name else name
            elif name in ('MASTER UP','MASTER DOWN'):
                if a.page in ('PATTERN GRID','GRID EDIT'):
                    a.pause_grid_follow();a.grid_voice=None
                    if a.grid_notes:a.grid_note=max(0,min(127,a.grid_note+(1 if name=='MASTER UP' else -1)))
                    else:a.pad=max(0,min(15,a.pad+(1 if name=='MASTER UP' else -1)))
                else:self.rotate(0,-1 if name=='MASTER UP' else 1)
            return
        if name in ('PAGE LEFT','PAGE RIGHT','MASTER LEFT','MASTER RIGHT') and a.page=='CHOP':
            if pressed:
                if name in self.held:return
                self.held.add(name)
                if a.shift:
                    a.slice_edit=False;self.change_page(1 if name.endswith('RIGHT') else -1)
                elif a.slice_ranges():
                    if not a.slice_edit and a.live_chop_started is not None:a.stop_live_chop()
                    a.slice_edit=True;a.focus_slice_boundary(name.endswith('RIGHT'))
            else:self.held.discard(name)
            return
        if name=='VARIATION':
            if pressed:self.variation_binding='GRID' if a.shift else 'NAVIGATE'
            binding=getattr(self,'variation_binding','NAVIGATE');shifted=a.shift
            # SHIFT chooses the binding; it must not turn GRID into SHIFT+GRID.
            a.shift=False
            try:return super().button(binding,pressed)
            finally:a.shift=shifted
        return super().button(name,pressed)
    def held_mode(self):
        mode=super().held_mode()
        # Events keeps PIN on button 1 and SELECT on button 4.
        return None if mode=='EVENTS' else mode

    def softkey(self,index):
        a=self.app
        if a.page in ('PATTERN GRID','GRID EDIT'):
            if index==0:
                from app.storage import save_json
                if 'EVENTS' in a.pinned_modes:a.pinned_modes.remove('EVENTS')
                else:a.pinned_modes.add('EVENTS')
                a.settings['pinned_modes']=sorted(a.pinned_modes)
                save_json(a.settings_path,a.settings)
                a.message='PIN ON' if 'EVENTS' in a.pinned_modes else 'PIN OFF'
                return
            if index==3:return super().softkey(0)
        return super().softkey(index)

    def softkeys(self):
        keys=super().softkeys()
        if self.app.page in ('PATTERN GRID','GRID EDIT'):
            keys=('PIN',)+keys[1:3]+(keys[0],)+keys[4:]
        if self.app.page=='OPTIONS':keys=keys[:2]+('GRID',)+keys[3:]
        return keys

    def fields(self):
        return super().fields()

    @on_controller('mk3')
    def rotate(self,index,delta):
        import time
        a=self.app
        if time.monotonic()<getattr(a,'update_lock_until',0):return
        if 1<=index<=8 and self.cursor_active() and self.fields()[index-1] is not None:self.cursors[self.cursor_key()]=index-1
        return super().rotate(index,delta)

    def cursor_active(self):
        from app.navigation import CONTROL_PAGES
        return self.source=='mk3' and self.app.page in CONTROL_PAGES+('AUDIO LOOP',) and not self.master_mode

    def cursor_key(self):
        a=self.app;sel=a.plugin_selected() if a.page=='PLUGIN' else None
        return (a.page,a.control_level,self.page_state()[0],(sel or {}).get('uri'))

    def populated(self):
        return [i for i,f in enumerate(self.fields()) if f is not None]

    def cursor_cell(self):
        if not self.cursor_active():return None
        cells=self.populated()
        if not cells:return None
        want=self.cursors.get(self.cursor_key(),cells[0])
        return min(cells,key=lambda c:(abs(c-want),c))

    def master_turn(self,delta):
        cell=self.cursor_cell()
        if cell is not None and not self.app.shift:self.rotate(cell+1,delta)
        else:self.rotate(0,delta)

    def page_directions(self):
        if self.app.page=='CHOP' and self.app.slice_ranges():return True,True
        return super().page_directions()

    def strip(self,value):
        self.strip_value=value
        if self.strip_mode=='PITCH':
            bend=8192 if value==0 else round((value-1)*16383/1023)
            self.app.actions.append(('controller_midi',(0xe0,(bend&127,bend>>7))))
        elif self.strip_mode=='MOD':
            if value:self.app.actions.append(('controller_midi',(0xb0,(1,round((value-1)*127/1023)))))
        elif self.strip_mode=='PERFORM':
            before=self.app.live_fx_pack();velocity=round(value*127/1024)
            self.app.live_fx_send(self.app.live_fx_pad+1 if self.app.live_fx_pad<15 else 0,velocity,pressed=bool(value))
            self.app.live_fx_record(before,self.app.live_fx_pack())
        elif self.strip_mode=='NOTES':
            # Glissando through the same keyboard mapping as the physical pads.
            slot=min(15,max(0,(value-1)*16//1024)) if value else None
            old=getattr(self,'strip_pad',None)
            if old!=slot:
                if old is not None:self.inputs.pad_off(self.source+'-strip',old)
                if slot is not None:self.inputs.pad_on(self.source+'-strip',slot,100)
                self.strip_pad=slot
    def disconnect(self):
        self.inputs.disconnect(self.source+'-strip');super().disconnect()

    def lock_parameters(self):
        """A/B performance parameters only; never restore notes, files or plug-in slots."""
        a=self.app
        targets=[a.project]+[v for g in a.project['groups'] for v in [g]+g['pads']]
        stored=getattr(self,'lock_state',None)
        if stored is None or stored[0]!=a.project_generation:
            data=[]
            for target in targets:
                values={k:copy.deepcopy(target[k]) for k in ('gain','sampler','routing','macros') if k in target}
                plugins=tuple((v['uri'],copy.deepcopy(v.get('controls',{})),v.get('bypass',False)) for v in target.get('plugins',[]))
                data.append((values,plugins))
            self.lock_state=(a.project_generation,data);a.message='PARAMETERS LOCKED';return
        a.remember()
        for target,(values,plugins) in zip(targets,stored[1]):
            for key,value in values.items():target[key]=copy.deepcopy(value)
            for current,(uri,controls,bypass) in zip(target.get('plugins',[]),plugins):
                if current['uri']==uri:current['controls']=copy.deepcopy(controls);current['bypass']=bypass
        self.lock_state=None;a.dirty=True;a.message='LOCK RESTORED'
