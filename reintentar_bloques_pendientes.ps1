$clips = @(
    @{ tema="Licenciatura en Negocios Digitales en la UMSA"; nombre_archivo="foco_grado_negocios_digitales";
       contexto="Dura 4 anios en modalidad virtual y otorga el titulo de Licenciado/a en Negocios Digitales. Combina contenidos economicos, administrativos y juridicos con competencias digitales: programacion basica y tecnologia aplicada. Tambien incluye formacion en habilidades blandas como liderazgo digital y autoconocimiento. Los egresados pueden desempenarse como lider de transformacion digital, consultor en estrategia digital, product manager, especialista en marketing digital, analista de business intelligence o emprendedor digital." },

    @{ tema="Doctorado en Fonoaudiologia - Posgrados UMSA"; nombre_archivo="posgrado_fonoaudiologia";
       contexto="La UMSA dicta el Doctorado en Fonoaudiologia en modalidad presencial, acreditado por CONEAU. Tambien ofrece especializaciones de posgrado en Atencion Temprana en Fonoaudiologia y en Audiologia. Estan pensados para fonoaudiologos que buscan profundizar en investigacion y practica clinica avanzada, con docentes de trayectoria reconocida." },

    @{ tema="Maestria en Bioetica - Posgrados UMSA"; nombre_archivo="posgrado_bioetica";
       contexto="La UMSA dicta la Maestria en Bioetica en modalidad presencial, acreditada por CONEAU. Esta pensada para profesionales de la salud, el derecho y otras disciplinas que necesiten abordar los dilemas eticos de la practica profesional y la investigacion, con docentes de trayectoria reconocida." },

    @{ tema="Maestria en Museologia Contemporanea - Posgrados UMSA"; nombre_archivo="posgrado_museologia";
       contexto="La UMSA dicta la Maestria en Museologia Contemporanea en modalidad a distancia, acreditada por CONEAU. Esta dirigida a profesionales vinculados a museos, centros culturales y patrimonio, que buscan actualizar su formacion en gestion y curaduria museistica con docentes de trayectoria reconocida." },

    @{ tema="Extension y Comunidad - vinculacion institucional de la UMSA"; nombre_archivo="extension_vinculacion_institucional";
       contexto="En las ultimas semanas la UMSA tuvo varias actividades de vinculacion institucional: participo del 10 aniversario de Path International Examinations el 7 de septiembre; recibio la visita del Procurador General Adjunto de la Ciudad de Buenos Aires el 1 de septiembre, en un encuentro con estudiantes y graduados de Abogacia; visito el Colegio de Traductores Publicos de la Ciudad de Buenos Aires el 27 de agosto; y recibio al Colegio de Traductores Publicos e Interpretes Regional San Isidro el 21 de agosto. Estas actividades muestran el vinculo permanente entre la universidad, el ejercicio profesional y la comunidad." }
)

foreach ($clip in $clips) {
    $payload = @{
        tema = $clip.tema
        contexto = $clip.contexto
        nombre_archivo = $clip.nombre_archivo
        voice_id = $null
        imagen_fondo = "media/placas/umsa_fondo.png"
        color_fondo = "black"
        agregar_a_playlist = $true
    } | ConvertTo-Json -Depth 5

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)

    Write-Host "Generando: $($clip.nombre_archivo) ..." -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/ai/clip" -Method Post -Body $bytes -ContentType "application/json; charset=utf-8"
        Write-Host "  OK -> en_playlist: $($resp.en_playlist)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR en $($clip.nombre_archivo): $_" -ForegroundColor Red
    }
}

Write-Host "Listo. Ahora corre POST /api/v1/stream/reload en Swagger para que el streamer relea la playlist." -ForegroundColor Yellow
