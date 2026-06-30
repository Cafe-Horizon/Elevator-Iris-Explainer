Shader "Custom/FloorMask" {
    Properties {
        _CircleRadius ("Circle Radius", Range(0,1)) = 0.5
    }
    SubShader {
        // 他の不透明オブジェクトより先に描画されるように設定
        Tags { "RenderType"="Opaque" "Queue"="Geometry-1" }

        // カラーバッファへの書き込みをオフにし、透明にする
        ColorMask 0
        ZWrite Off

        Stencil {
            Ref 2           // ステンシル番号を指定
            Comp Always     // 常にテストに合格させる
            Pass Replace    // テスト合格時、バッファをRefの値に置き換える
        }

        Pass {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
            };

            float _CircleRadius;

            v2f vert (appdata v) {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target {
                float dist = distance(i.uv, float2(0.5, 0.5));
                clip(_CircleRadius - dist);
                return fixed4(0,0,0,0);
            }
            ENDCG
        }
    }
}