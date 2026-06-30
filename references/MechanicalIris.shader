Shader "Custom/MechanicalIris"
{
    Properties
    {
        // 羽根のベースカラー(画像が切り抜かれた外側の色)
        _Color ("Blade Color", Color) = (0.2, 0.2, 0.2, 1)

        [Header(Profile Picture)]
        _ProfileTex ("Profile Picture (RGB)", 2D) = "white" {}
        _ProfileColor ("Profile Color Tint", Color) = (1, 1, 1, 1)
        _ProfileScale ("Profile Scale", Range(0, 2)) = 0.9
        
        [Header(Common Settings)]
        _Glossiness ("Smoothness", Range(0,1)) = 0.3
        _Metallic ("Metallic", Range(0,1)) = 0.0
        
        _MaxAngle ("Max Angle (Deg)", Float) = 60
        _Open ("Open Amount", Range(0, 1)) = 0.0
        _FlushAmount ("Flush Amount", Range(0, 1)) = 0.0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 200

        Stencil {
            Ref 2           // ステンシル番号を指定
            Comp Equal   // ステンシルバッファの値が等しい場合のみ描画
            Pass Keep       // バッファの値は書き換えずに維持する
        }
        
        Cull Off 

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert addshadow
        #pragma target 3.0

        sampler2D _ProfileTex;

        struct Input
        {
            float2 uv_ProfileTex; 
            float3 localPos;
        };

        half _Glossiness;
        half _Metallic;
        fixed4 _Color;
        fixed4 _ProfileColor;
        float _ProfileScale;
        float _Open;
        float _MaxAngle;
        float _FlushAmount;

        void vert (inout appdata_full v, out Input o) {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            float multiplier = lerp(1.0, max(0.001, 1.0 - _FlushAmount), step(0.707, v.normal.y));
            v.vertex.y *= multiplier;

            // ピボット位置の計算(頂点カラーを-2～2の範囲に変換)
            float2 pivot = (v.color.rg * 4.0) - 2.0;
            float angle = _Open * _MaxAngle * (3.1415926535 / 180.0);

            float cosA = cos(angle);
            float sinA = sin(angle);

            float3 pos = v.vertex.xyz;
            
            // モデルの向きに応じて、XZ平面またはXY平面での回転を行う
            pos.x -= pivot.x;
            pos.z -= pivot.y;

            float newX = pos.x * cosA - pos.z * sinA;
            float newZ = pos.x * sinA + pos.z * cosA;
            pos.x = newX;
            pos.z = newZ;

            pos.x += pivot.x;
            pos.z += pivot.y;
            v.vertex.xyz = pos;
            o.localPos = pos;

            // 法線の回転
            float3 norm = v.normal;
            float nX = norm.x * cosA - norm.z * sinA;
            float nZ = norm.x * sinA + norm.z * cosA;
            norm.x = nX;
            norm.z = nZ;
            v.normal = normalize(norm);
            
            // 接線(Tangent)の回転
            float4 tan = v.tangent;
            float tX = tan.x * cosA - tan.z * sinA;
            float tZ = tan.x * sinA + tan.z * cosA;
            tan.x = tX;
            tan.z = tZ;
            v.tangent = tan;
        }

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            // ローカル座標系でのクリッピング(中心からの距離)
            float distToCenter = length(IN.localPos.xz);
            clip(1.0 - distToCenter);

            // UVを中心からスケール調整
            float2 centeredUV = IN.uv_ProfileTex - 0.5;
            float2 scaledUV = (centeredUV / _ProfileScale) + 0.5;

            // プロフィール画像を読み込む
            fixed4 texColor = tex2D (_ProfileTex, scaledUV);
            fixed4 profileColor = texColor * _ProfileColor;

            // スケール調整後のUV座標でマスクを計算
            float dist = distance(scaledUV, float2(0.5, 0.5));
            float mask = step(dist, 0.5);

            // 枠外のテクスチャ(リピート等)を弾くためのガード (Branchless)
            mask *= step(0, scaledUV.x) * step(scaledUV.x, 1) * step(0, scaledUV.y) * step(scaledUV.y, 1);

            // マスクが1ならプロフィール画像、0なら羽根のベースカラー(_Color)を表示
            o.Albedo = lerp(_Color.rgb, profileColor.rgb, mask);

            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            o.Alpha = _Color.a;
        }
        ENDCG

        // ShadowCaster Pass
        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }

            CGPROGRAM
            #pragma vertex vert_shadow
            #pragma fragment frag_shadow
            #pragma multi_compile_shadowcaster
            #include "UnityCG.cginc"

            float _Open;
            float _MaxAngle;
            float _FlushAmount;

            struct v2f_shadow {
                V2F_SHADOW_CASTER;
                float3 localPos : TEXCOORD1;
            };

            v2f_shadow vert_shadow (appdata_full v) {
                v2f_shadow o;

                // 上面のみに影響を与える(Branchless)
                float multiplier = lerp(1.0, max(0.001, 1.0 - _FlushAmount), step(0.707, v.normal.y));
                v.vertex.y *= multiplier;

                // メインパスと同じ頂点変形を適用
                float2 pivot = (v.color.rg * 4.0) - 2.0;
                float angle = _Open * _MaxAngle * (3.1415926535 / 180.0);
                float cosA = cos(angle);
                float sinA = sin(angle);

                float3 pos = v.vertex.xyz;
                pos.x -= pivot.x;
                pos.z -= pivot.y;
                float newX = pos.x * cosA - pos.z * sinA;
                float newZ = pos.x * sinA + pos.z * cosA;
                pos.x = newX;
                pos.z = newZ;
                pos.x += pivot.x;
                pos.z += pivot.y;
                
                v.vertex.xyz = pos;
                o.localPos = pos;

                TRANSFER_SHADOW_CASTER_NORMALOFFSET(o)
                return o;
            }

            float4 frag_shadow (v2f_shadow i) : SV_Target {
                // 頂点シェーダーで計算された localPos は回転後のオブジェクト空間座標
                // そのため、ここでは単純に (1.0 - length(i.localPos.xz)) で判定すれば
                // オブジェクトのスケールに追従したクリッピングとなる
                float distToCenter = length(i.localPos.xz);
                clip(1.0 - distToCenter);

                SHADOW_CASTER_FRAGMENT(i)
            }
            ENDCG
        }
    }
    FallBack "Diffuse"
}
