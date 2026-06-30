import bpy
import bmesh
import math
from mathutils import Vector, Matrix

bpy.ops.object.select_all(action='DESELECT')

mesh = bpy.data.meshes.new("MechanicalIris_Mesh")
obj = bpy.data.objects.new("MechanicalIris", mesh)
bpy.context.collection.objects.link(obj)

bm = bmesh.new()

num_blades = 6
pivot_dist = 1.2
profile_radius = 1.0  # プロフィール画像の半径

# 頂点カラーと「1つのUVレイヤー」を作成
color_layer = bm.loops.layers.color.new("PivotData")
uv_layer = bm.loops.layers.uv.new("UVMap")  # UV0: プロフィール画像用のみ

for i in range(num_blades):
    angle = i * (2.0 * math.pi / num_blades)
    rot_z = Matrix.Rotation(angle, 4, 'Z')

    pivot_local = Vector((pivot_dist, 0.0, 0.0))
    pivot_world = rot_z @ pivot_local

    # ピボット座標を頂点カラーに保存
    r = (pivot_world.x + 2.0) / 4.0
    g = (pivot_world.y + 2.0) / 4.0
    b = 0.0
    a = 1.0

    v_coords = [
        (0.0, 0.0),
        (0.4, 1.2),
        (1.6, 1.3),
        (1.8, -0.2),
        (0.4, -0.5)
    ]

    face_verts = []
    for coord in v_coords:
        z = coord[1] * 0.03  # 重なり防止の傾き
        v_local = Vector((coord[0], coord[1], z))
        v_world = rot_z @ v_local
        face_verts.append(bm.verts.new(v_world))

    face = bm.faces.new(face_verts)

    for idx, loop in enumerate(face.loops):
        loop[color_layer] = (r, g, b, a)

        # UVMap プロフィール画像用（閉じた状態のワールド座標ベース）
        # Blenderの中心(0,0)を基準に、直径2mの円がUVの(0~1)に収まるようにマッピング
        v_world_closed = loop.vert.co
        u_prof = (v_world_closed.x / (profile_radius * 2.0)) + 0.5
        v_prof = (v_world_closed.y / (profile_radius * 2.0)) + 0.5
        loop[uv_layer].uv = (u_prof, v_prof)

bm.to_mesh(mesh)
bm.free()

bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bm.to_mesh(mesh)
bm.free()

print("メカニカルアイリスを生成しました。多分ヨシ！")
