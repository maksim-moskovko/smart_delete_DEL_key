import bpy

bl_info = {
    "name": "Smart Delete (DEL key)",
    "description": "Auto detect and delete elements. Replace DEL key, but keep X key",
    "author": "Vladislav Kindushov (Darcvizer), Reiner 'Tiles' Prokein, Draise (Trinumedia), qwen, noanymous",
    "version": (1, 1),
    "blender": (4, 5, 0),
    "doc_url": "https://github.com/Bforartists/Manual",
    "tracker_url": "https://github.com/Bforartists/Bforartists",
    "support": "OFFICIAL",
    "category": "Bforartists",
}

# Store keymap items for cleanup
addon_keymaps = []

def find_connected_verts(me, found_index):  
    edges = me.edges  
    connecting_edges = [i for i in edges if found_index in i.vertices[:]]  
    return len(connecting_edges)  

class SDEL_OT_meshdissolvecontextual(bpy.types.Operator):
    """ Dissolves mesh elements based on context instead
    of forcing the user to select from a menu what
    it should dissolve.
    """
    bl_idname = "mesh.dissolve_contextual_bfa"
    bl_label = "Smart Delete"
    bl_options = {'UNDO'}
   
    use_verts: bpy.props.BoolProperty(name="Use Verts", default=False)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None) and (context.mode == "EDIT_MESH")
   
    def execute(self, context):
        if bpy.context.mode == 'EDIT_MESH':
            select_mode = context.tool_settings.mesh_select_mode
            me = context.object.data
            mymode = 0  # Local variable for mode tracking

            # Vertices select
            if select_mode[0]:
                mymode = 0

                # Dissolve vertices with error handling
                if bpy.ops.mesh.dissolve_verts.poll():
                    try:
                        bpy.ops.mesh.dissolve_verts()

                        # Check for single vertex
                        bpy.ops.object.mode_set(mode='OBJECT')
                        remaining_verts = [v for v in me.vertices if v.select]
                        if len(remaining_verts) == 1:
                            me.vertices[remaining_verts[0].index].select = True
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.delete(type='VERT')
                        else:
                            bpy.ops.object.mode_set(mode='EDIT')

                        # Check for all vertices
                        bpy.ops.object.mode_set(mode='OBJECT')
                        all_verts = [v for v in me.vertices]
                        if len(remaining_verts) == len(all_verts):
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.delete(type='VERT')
                        else:
                            bpy.ops.object.mode_set(mode='EDIT')

                        # Check for two disconnected vertices
                        selected_verts = [v for v in me.vertices if v.select]
                        if len(selected_verts) == 2:
                            connected_edges = [e for e in me.edges if any(v.index in e.vertices for v in selected_verts)]
                            if not connected_edges:
                                bpy.ops.object.mode_set(mode='EDIT')
                                bpy.ops.mesh.delete(type='VERT')
                            else:
                                bpy.ops.object.mode_set(mode='EDIT')

                        # Check for two vertices
                        if len(remaining_verts) == 2:
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.delete(type='VERT')
                        else:
                            bpy.ops.object.mode_set(mode='EDIT')

                    except RuntimeError as exception:
                        error = " ".join(exception.args)
                        self.report({'ERROR'}, "Invalid boundary region to join faces. You cannot delete this geometry that way. Try another delete method or selection")

            # Edge select
            elif select_mode[1] and not select_mode[2]:
                mymode = 1

                bpy.ops.object.mode_set(mode='OBJECT')
                selected_edges = [e for e in me.edges if e.select]
                all_edges = [e for e in me.edges]

                # Check if all edges selected
                if len(selected_edges) == len(all_edges):
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.delete(type='EDGE')
                else:
                    # Check if selected edges form an island
                    island_edges = set()
                    edges_to_check = set(selected_edges)
                    while edges_to_check:
                        edge = edges_to_check.pop()
                        if edge not in island_edges:
                            island_edges.add(edge)
                            connected_edges = [e for e in me.edges 
                                              if any(v in edge.vertices for v in e.vertices) 
                                              and e not in island_edges]
                            edges_to_check.update(connected_edges)
                    
                    if len(selected_edges) == len(island_edges):
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.delete(type='EDGE')
                    else:
                        # Check for edge with no connections
                        no_connecting_edges = all(
                            find_connected_verts(me, v) == 1 
                            for e in selected_edges 
                            for v in e.vertices
                        )
                        if no_connecting_edges:
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.delete(type='EDGE')
                        else:
                            # Handle small edge counts
                            if len(all_edges) in [3, 4, 5] or len(island_edges) in [3, 4, 5]:
                                bpy.ops.object.mode_set(mode='EDIT')
                                bpy.ops.mesh.delete(type='EDGE_FACE')
                            else:
                                # Standard dissolve with fallback for boundary edges
                                bpy.ops.object.mode_set(mode='EDIT')
                                try:
                                    bpy.ops.mesh.dissolve_edges(use_verts=self.use_verts)
                                except RuntimeError as e:
                                    # Fallback to edge deletion if dissolve fails
                                    if "Invalid boundary region" in str(e):
                                        bpy.ops.mesh.delete(type='EDGE')
                                    else:
                                        raise
                                else:
                                    # Only run cleanup if dissolve succeeded
                                    bpy.ops.mesh.select_mode(type='VERT')
                                    bpy.ops.object.mode_set(mode='OBJECT')
                                    vs = [v.index for v in me.vertices if v.select]
                                    
                                    # FIX: Use direct data access instead of operators
                                    # Deselect all vertices using direct data access (not operators)
                                    for v in me.vertices:
                                        v.select = False
                                    
                                    # Select vertices with exactly 2 connecting edges
                                    for v in vs:
                                        if v < len(me.vertices) and find_connected_verts(me, v) == 2:
                                            me.vertices[v].select = True
                                    
                                    # Set back to edit mode for dissolve operation
                                    bpy.ops.object.mode_set(mode='EDIT')
                                    bpy.ops.mesh.dissolve_verts()
                                    
                                    # FIX: Use direct data access for final deselect
                                    bpy.ops.object.mode_set(mode='OBJECT')
                                    for v in me.vertices:
                                        v.select = False
                                    for v in vs:
                                        if v < len(me.vertices):
                                            me.vertices[v].select = True
                                    bpy.ops.object.mode_set(mode='EDIT')

            # Face Select
            elif select_mode[2] and not select_mode[1]:
                mymode = 2 
                bpy.ops.mesh.delete(type='FACE')
            # Dissolve Vertices
            else:
                bpy.ops.mesh.dissolve_verts()
                
            # Restore previous select mode - FIXED
            if mymode == 1:
                # Only try to set edge mode if we're still in edit mode with a valid mesh
                if context.mode == 'EDIT_MESH' and context.object and context.object.type == 'MESH':
                    try:
                        bpy.ops.mesh.select_mode(type='EDGE')
                    except RuntimeError:
                        # Ignore if context is invalid (e.g., mesh was completely deleted)
                        pass
                
        return {'FINISHED'}

classes = (SDEL_OT_meshdissolvecontextual, )

def menu_func(self, context):
    self.layout.operator(SDEL_OT_meshdissolvecontextual.bl_idname, icon="DELETE")

def register_keymaps():
    """Register keymap for Delete/X keys in Mesh Edit Mode"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc is None:
        return
    
    # Get the Mesh keymap (this is the correct keymap for edit mode operations)
    km = kc.keymaps.get('Mesh')
    if km is None:
        # If not found, try to get it from the default keyconfig
        kc = wm.keyconfigs.default
        km = kc.keymaps.get('Mesh')
        if km is None:
            return
    
    # Keys to override (DEL and X)
    keys = ['DEL']
    
    # Remove existing keymap items for these keys if they exist
    for kmi in km.keymap_items:
        if kmi.idname in ['mesh.delete', SDEL_OT_meshdissolvecontextual.bl_idname] and kmi.type in keys:
            km.keymap_items.remove(kmi)
    
    # Add new keymap items for our operator
    for key in keys:
        kmi = km.keymap_items.new(
            SDEL_OT_meshdissolvecontextual.bl_idname,
            key,
            'PRESS'
        )
        kmi.active = True
        addon_keymaps.append(kmi)

def unregister_keymaps():
    """Remove our keymap items - fixed to avoid membership test error"""
    wm = bpy.context.window_manager
    keyconfigs = [wm.keyconfigs.addon, wm.keyconfigs.default]
    
    # Process each keymap item we added
    for kmi in addon_keymaps[:]:
        removed = False
        # Try to remove from both keyconfigs
        for kc in keyconfigs:
            if kc is None:
                continue
            km = kc.keymaps.get('Mesh')
            if km is None:
                continue
            try:
                km.keymap_items.remove(kmi)
                removed = True
                break  # Stop after first successful removal
            except (RuntimeError, ReferenceError):
                # Item not found or invalid - continue to next keyconfig
                pass
        
        # Always remove from our tracking list
        addon_keymaps.remove(kmi)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)
    
    # Register keymaps
    register_keymaps()

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)
    
    # Unregister keymaps
    unregister_keymaps()

if __name__ == "__main__":
    register()