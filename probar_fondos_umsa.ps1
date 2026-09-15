# Prueba de concepto: regenera 2 clips usando como fondo una captura real
# de la pagina de la UMSA correspondiente a cada tema (en vez del logo
# generico umsa_fondo.png que usaban todos los clips hasta ahora).
#
# Las 11 imagenes ya estan en media/placas/ (una por clip, bajada del
# header/nota real de umsa.edu.ar). Este script prueba con 2 nada mas
# (foco_grado_abogacia y posgrado_fonoaudiologia) para que puedas revisar
# el resultado antes de regenerar los otros 9 y gastar mas llamadas de
# Anthropic + Piper.
#
# Si el streamer ya esta corriendo, despues de esto hace falta
# POST /api/v1/stream/reload en Swagger para que tome los clips nuevos.

# Cambiá $ApiBase a la URL de Railway para correr esto contra producción.
# Si configuraste ADMIN_TOKEN, seteá $env:ADMIN_TOKEN antes de correr el
# script; si no, dejalo vacío (funciona igual que antes en local).
$ApiBase = "http://127.0.0.1:8000"
$AdminToken = $env:ADMIN_TOKEN
$Headers = @{}
if ($AdminToken) { $Headers["X-Admin-Token"] = $AdminToken }

$clips = @(
    @{ tema="Carrera de Abogacia en la UMSA"; nombre_archivo="foco_grado_abogacia";
       contexto="Es una carrera de 5 anios que otorga el titulo de Abogado/a. Modalidad presencial o virtual. Prepara para patrocinar y representar a las partes en procedimientos judiciales y administrativos, ejercer funciones jurisdiccionales, emitir dictamenes juridicos y actuar como sindico en sociedades. El plan de estudios tiene fuerte formacion practica: talleres de litigacion, redaccion de escritos judiciales, analisis jurisprudencial y clinicas legales que simulan el ejercicio profesional real, ademas de incorporar herramientas de inteligencia artificial y gestion documental.";
       imagen_fondo="media/placas/foco_grado_abogacia.jpeg" },

    @{ tema="Doctorado en Fonoaudiologia - Posgrados UMSA"; nombre_archivo="posgrado_fonoaudiologia";
       contexto="La UMSA dicta el Doctorado en Fonoaudiologia en modalidad presencial, acreditado por CONEAU. Tambien ofrece especializaciones de posgrado en Atencion Temprana en Fonoaudiologia y en Audiologia. Estan pensados para fonoaudiologos que buscan profundizar en investigacion y practica clinica avanzada, con docentes de trayectoria reconocida.";
       imagen_fondo="media/placas/posgrado_fonoaudiologia.png" }
)

foreach ($clip in $clips) {
    $payload = @{
        tema = $clip.tema
        contexto = $clip.contexto
        nombre_archivo = $clip.nombre_archivo
        voice_id = $null
        imagen_fondo = $clip.imagen_fondo
        color_fondo = "black"
        agregar_a_playlist = $true
    } | ConvertTo-Json -Depth 5

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)

    Write-Host "Generando: $($clip.nombre_archivo) con fondo $($clip.imagen_fondo) ..." -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "$ApiBase/api/v1/ai/clip" -Method Post -Body $bytes -ContentType "application/json; charset=utf-8" -Headers $Headers
        Write-Host "  OK -> en_playlist: $($resp.en_playlist)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR en $($clip.nombre_archivo): $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Listo. Revisa los 2 videos nuevos en media/videos/ (foco_grado_abogacia.mp4 y posgrado_fonoaudiologia.mp4)." -ForegroundColor Yellow
Write-Host "Si el fondo se ve bien, avisame y genero el script para los otros 9 clips." -ForegroundColor Yellow
