"""MK3 controller profile actions and the parameter cursor they drive."""

class CursorState:
    """Parameter cursor per layout; Mk3Surface.__init__ creates self.cursors."""
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

STEPS={'transport.back':-1,'transport.forward':1}
MOVES={'cursor.previous':'move_cursor','cursor.next':'move_cursor','page.previous':'change_page','page.next':'change_page'}

def run(surface,action,index,delta):
    """Perform one profile action. True = acted; False = not applicable, or cursor.follow letting the original continue."""
    if action=='cursor.edit':
        cell=surface.cursor_cell()
        if cell is None:return False
        surface.rotate(cell+1,delta);return True
    if action.startswith('edit.knob'):
        n=int(action[9:])
        if surface.fields()[n-1] is None:return False
        surface.rotate(n,delta);return True
    if action=='transport.move':surface.rotate(0,delta);return True
    if action in STEPS:surface.rotate(0,STEPS[action]);return True
    if action in MOVES:getattr(surface,MOVES[action])(-1 if action.endswith('previous') else 1);return True
    if action in ('chain.previous','chain.next'):return surface.switch_chain(-1 if action=='chain.previous' else 1)
    if action=='cursor.follow':
        if surface.fields()[index-1] is not None:surface.cursors[surface.cursor_key()]=index-1
        return False
    raise ValueError(f'unknown action {action!r}')
