Shader "Hidden/VitureXR/OESBlit"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" }
        LOD 100

        Cull Off
        ZWrite Off
        ZTest Always

        // Android OES: Required for camera feed on device (GL_TEXTURE_EXTERNAL_OES)
        Pass
        {
            GLSLPROGRAM

            #ifdef VERTEX
            varying vec2 texCoord;
            void main()
            {
                gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
                texCoord = gl_MultiTexCoord0.xy;
                texCoord.y = 1.0 - texCoord.y;
            }
            #endif

            #ifdef FRAGMENT
            #if __VERSION__ >= 300
            #extension GL_OES_EGL_image_external_essl3 : require
            #define TEXTURE_EXTERNAL texture
            #else
            #extension GL_OES_EGL_image_external : require
            #define TEXTURE_EXTERNAL texture2D
            #endif
            varying vec2 texCoord;
            uniform samplerExternalOES _MainTex;
            void main()
            {
                vec4 c = TEXTURE_EXTERNAL(_MainTex, texCoord);
                gl_FragColor = vec4(c.rgb, 1.0);
            }
            #endif

            ENDGLSL
        }
    }

    // URP fallback: No URP SubShader - HLSL cannot use samplerExternalOES.
    // Unity will use the GLSL SubShader above for Graphics.Blit on Android.
    // This ensures OES camera texture displays correctly in both Built-in and URP projects.
    Fallback Off
}
