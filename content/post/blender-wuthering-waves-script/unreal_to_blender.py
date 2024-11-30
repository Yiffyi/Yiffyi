import bpy
import mathutils
import re
import bmesh


class UE2BL_OT_button_context_test(bpy.types.Operator):
    """Right click entry test"""
    bl_idname = "ue2bl.button_context_test"
    bl_label = "UE->Blender: 测试"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        value = getattr(context, "button_pointer", None)
        if value is not None:
            dump(value, "button_pointer")

        value = getattr(context, "button_prop", None)
        if value is not None:
            dump(value, "button_prop")

        value = getattr(context, "button_operator", None)
        if value is not None:
            dump(value, "button_operator")

        return {'FINISHED'}


class UE2BL_OT_button_armature_transform(bpy.types.Operator):
    """Right click entry test"""
    bl_idname = "ue2bl.button_armature_transform"
    bl_label = "UE->Blender: 骨骼旋转"
    bl_description = "选中骨架后进行操作"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Get the active armature
        armature = bpy.context.active_object
        return armature is not None and armature.type == 'ARMATURE'

    def convert_unreal_to_blender_bones(self):
        """
        Converts bone matrix from Unreal coordinate system (+Z=Up, +X=Front, +Y=Right)
        to Blender coordinate system (+Z=Up, -Y=Front, -X=Right)
        """
        # Get the active armature
        armature = bpy.context.active_object
        
        if armature is None or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}

        # Enter Edit Mode to modify bone transformations
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Rotation matrix to convert coordinate systems
        conversion_matrix = mathutils.Matrix([
            [0, 1, 0, 0],
            [-1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        
        cnt = 0
        # Iterate through all bones in the armature
        for bone in armature.data.edit_bones:
            # Apply the coordinate system conversion to the bone's matrix
            bone.matrix = bone.matrix @ conversion_matrix
            cnt += 1
        
        # Return to Object Mode
        bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, f"骨骼旋转完成，共{cnt}根")
        # print("Bone coordinate system conversion complete!")
        return {'FINISHED'}

    def execute(self, context):
        return self.convert_unreal_to_blender_bones()


class UE2BL_OT_button_action_transform(bpy.types.Operator):
    """Right click entry test"""
    bl_idname = "ue2bl.button_action_transform"
    bl_label = "UE->Blender: 动画数据变换"
    bl_description = "选中骨架后进行操作"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Get the active armature
        armature = bpy.context.active_object
        return armature is not None and armature.type == 'ARMATURE'

    def convert_unreal_to_blender_actions(self):
        """
        Converts quaternion action data from Unreal coordinate system to Blender coordinate system
        
        Args:
            target_object (bpy.types.Object, optional): Object to filter actions. 
                                                        If None, converts all actions.
        """
        target_object = bpy.context.active_object

        if target_object is None or target_object.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}

        # Get actions linked to the object
        if target_object:
            # Collect actions from various potential sources
            actions_to_convert = set()

            # Check Object Animation Data
            if target_object.animation_data and target_object.animation_data.action:
                actions_to_convert.add(target_object.animation_data.action)
            
            # Check Object's NLA Tracks
            if target_object.animation_data:
                for track in target_object.animation_data.nla_tracks:
                    for strip in track.strips:
                        if strip.action:
                            actions_to_convert.add(strip.action)

            for action in bpy.data.actions:
                if action.name.endswith(target_object.name):
                    actions_to_convert.add(action)

            print(f"Found {len(actions_to_convert)} actions for object: {target_object.name}")
        else:
            # If no object is selected, convert all actions in the project
            actions_to_convert = bpy.data.actions
            print(f"Found {len(actions_to_convert)} actions in the project")
        
        # Iterate through collected actions
        for action in actions_to_convert:
            print(f"Converting action: {action.name}")

            # Collect keyframes for X and Y components
            r_x_keyframes = dict()
            r_y_keyframes = dict()
            d_x_keyframes = dict()
            d_y_keyframes = dict()
            
            # First, collect keyframe data
            for fcurve in action.fcurves:
                path = fcurve.data_path
                if path.endswith('rotation_quaternion'):
                    bone_path = path[:-len('rotation_quaternion')]
                    if fcurve.array_index == 1:  # X component
                        r_x_keyframes[bone_path] = [(kf.co[0], kf.co[1]) for kf in fcurve.keyframe_points]
                    elif fcurve.array_index == 2:  # Y component
                        r_y_keyframes[bone_path] = [(kf.co[0], kf.co[1]) for kf in fcurve.keyframe_points]
                elif path.endswith('location'):
                    bone_path = path[:-len('location')]
                    if fcurve.array_index == 0:  # X component
                        d_x_keyframes[bone_path] = [(kf.co[0], kf.co[1]) for kf in fcurve.keyframe_points]
                    elif fcurve.array_index == 1:  # Y component
                        d_y_keyframes[bone_path] = [(kf.co[0], kf.co[1]) for kf in fcurve.keyframe_points]
            
            # if len(x_keyframes) != len(y_keyframes):
            #     print(f"Keyframe Mismatch")

            # Now modify the fcurves
            for fcurve in action.fcurves:
                path = fcurve.data_path
                if path.endswith('rotation_quaternion'):
                    bone_path = path[:-len('rotation_quaternion')]

                    if len(r_y_keyframes[bone_path]) != len(r_x_keyframes[bone_path]):
                        self.report({'WARNING'}, f"{path} 的 X、Y 分量的关键帧数量不同")

                    for i, kf in enumerate(fcurve.keyframe_points):
                        # Swap X and Y components
                        if fcurve.array_index == 1:  # X component
                            # Find corresponding Y keyframe value
                            kf.co[0] = r_y_keyframes[bone_path][i][0]
                            kf.co[1] = -r_y_keyframes[bone_path][i][1]
                        elif fcurve.array_index == 2:  # Y component
                            # Find corresponding X keyframe value
                            kf.co[0] = r_x_keyframes[bone_path][i][0]
                            kf.co[1] = r_x_keyframes[bone_path][i][1]

                elif path.endswith('location'):
                    bone_path = path[:-len('location')]               
     
                    if len(d_y_keyframes[bone_path]) != len(d_x_keyframes[bone_path]):
                        self.report({'WARNING'}, f"{path} 的 X、Y 分量的关键帧数量不同")

                    for i, kf in enumerate(fcurve.keyframe_points):
                        # Swap X and Y components
                        if fcurve.array_index == 0:  # X component
                            # Find corresponding Y keyframe value
                            kf.co[0] = d_y_keyframes[bone_path][i][0]
                            kf.co[1] = -d_y_keyframes[bone_path][i][1]
                        elif fcurve.array_index == 1:  # Y component
                            # Find corresponding X keyframe value
                            kf.co[0] = d_x_keyframes[bone_path][i][0]
                            kf.co[1] = d_x_keyframes[bone_path][i][1]

        print("Action data coordinate system conversion complete!")
        self.report({'INFO'}, f"动画数据变换结束，共处理 {len(actions_to_convert)} 个")
        return {'FINISHED'}

    def execute(self, context):
        return self.convert_unreal_to_blender_actions()


class UE2BL_OT_button_merge_morph_meshes(bpy.types.Operator):
    """Right click entry test"""
    bl_idname = "ue2bl.button_merge_morph_meshes"
    bl_label = "UE->Blender: 合并形态键"
    bl_description = "选中网格体后进行操作"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        base_object = bpy.context.active_object
        return base_object is not None and base_object.type == 'MESH'

    def merge_morphs_to_base_mesh(self):
        """
        Merge all meshes named with {base_mesh}_Morph* into the base mesh using shape keys
        """
        # Find the selected base mesh
        base_object = bpy.context.active_object
        if not base_object or base_object.type != 'MESH':
            self.report({'WARNING'}, "请先选中网格体")
            return {'CANCELLED'}

        # Ensure basis shape key exists
        if not base_object.data.shape_keys:
            base_object.shape_key_add(name='Basis', from_mix=False)

        # Extract base mesh name (removing any trailing numbers)
        base_name_pattern = re.sub(r'.?\d+$', '', base_object.name)

        # Find all morph meshes
        morph_objects = [
            obj for obj in bpy.data.objects 
            if obj != base_object and 
            obj.type == 'MESH' and 
            obj.name.startswith(f"{base_name_pattern}_Morph")
        ]

        if not morph_objects:
            self.report({'WARNING'}, "没有找到对应的 Morph，请检查 Morph 的名称格式是否为 基础模型_Morph*")
            return {'CANCELLED'}

        # Create a new bmesh from the base object
        base_bm = bmesh.new()
        base_bm.from_mesh(base_object.data)

        # Process each morph mesh
        for morph_obj in morph_objects:
            # Create a temporary bmesh for the morph
            morph_bm = bmesh.new()
            morph_bm.from_mesh(morph_obj.data)

            # Ensure vertex counts match
            if len(morph_bm.verts) != len(base_bm.verts):
                morph_bm.free()
                base_bm.free()
                self.report({'ERROR'}, f"Morph 网格体的顶点数与基础网格体不同（{len(morph_bm.verts)} != {len(base_bm.verts)}）")
                return {'CANCELLED'}

            # Remove prefix for shape key name
            shape_key_name = re.sub(f"^{base_name_pattern}_Morph\d+_", '', morph_obj.name)
            
            # Add shape key
            shape_key = base_object.shape_key_add(name=shape_key_name, from_mix=False)

            # Transfer vertex positions to shape key
            for i, v in enumerate(morph_bm.verts):
                shape_key.data[i].co = v.co

            # Clean up morph bmesh
            morph_bm.free()

        # Update base mesh
        # base_bm.to_mesh(base_object.data)
        base_bm.free()
        base_object.data.update()

        # Remove morph objects
        bpy.ops.object.select_all(action='DESELECT')
        for morph_obj in morph_objects:
            morph_obj.select_set(True)
        bpy.ops.object.delete()

        # Select and make active the base object
        base_object.select_set(True)
        bpy.context.view_layer.objects.active = base_object

        self.report({'INFO'}, f"合并完成，{base_object.name} 现包含 {len(morph_objects)+1} 个形态键")
        return {'FINISHED'}

    def execute(self, context):
        return self.merge_morphs_to_base_mesh()

classes = {
    UE2BL_OT_button_context_test,
    UE2BL_OT_button_armature_transform,
    UE2BL_OT_button_action_transform,
    UE2BL_OT_button_merge_morph_meshes
}

def draw_menu(self, context):
    layout = self.layout
    layout.separator()

    for c in classes:
        layout.operator(c.bl_idname)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_object_context_menu.append(draw_menu)
    bpy.types.OUTLINER_MT_object.append(draw_menu)


def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_menu)
    bpy.types.OUTLINER_MT_object.remove(draw_menu)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
