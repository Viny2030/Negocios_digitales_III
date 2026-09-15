# Regenera los 9 clips restantes con el fondo real de la pagina de UMSA
# correspondiente a cada tema (los otros 2 -foco_grado_abogacia y
# posgrado_fonoaudiologia- ya se hicieron y se verificaron con
# probar_fondos_umsa.ps1). Las 11 imagenes ya estan en media/placas/.
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
    @{ tema="Carrera de Contador Publico en la UMSA"; nombre_archivo="foco_grado_contador_publico";
       contexto="Dura 4 anios en modalidad presencial y otorga el titulo de Contador Publico. Forma profesionales para el asesoramiento, la planificacion y el control de la actividad contable, tributaria, societaria y de gestion economica y financiera en organizaciones publicas y privadas. Combina contabilidad avanzada con derecho economico y legislacion laboral, incluye materias de sistemas de informacion y auditoria de sistemas computarizados, y ofrece dos modulos de practica profesional supervisada en el cuarto anio.";
       imagen_fondo="media/placas/foco_grado_contador_publico.png" },

    @{ tema="Licenciatura en Artes Visuales en la UMSA"; nombre_archivo="foco_grado_artes_visuales";
       contexto="Dura 4 anios en modalidad presencial y otorga el titulo de Licenciado/a en Artes Visuales. Ofrece una formacion integral en cuatro especialidades: pintura, grabado, escultura y nuevos medios. Los egresados trabajan en producciones artisticas individuales y colectivas, museos, galerias y centros culturales, cine, animacion, teatro, escenografia, disenio grafico y docencia. El plan incluye investigacion visual y laboratorios de imagen, con posibilidad de especializarse en fotografia, narrativa audiovisual y arte multimedial.";
       imagen_fondo="media/placas/foco_grado_artes_visuales.png" },

    @{ tema="Licenciatura en Psicologia en la UMSA"; nombre_archivo="foco_grado_psicologia";
       contexto="Dura 4 anios y medio, incluyendo practicas profesionales supervisadas en el tramo final, y otorga el titulo de Licenciado/a en Psicologia. Se organiza en cinco areas: clinica, laboral, forense, educacional y comunitaria. Los egresados trabajan en hospitales y centros terapeuticos, consultorios privados, recursos humanos, el ambito educativo, organismos gubernamentales y ONGs. El plan incluye materias como psicodiagnostico, psicoterapias breves y terapia sistemica, y fomenta la participacion en proyectos de investigacion desde los primeros anios.";
       imagen_fondo="media/placas/foco_grado_psicologia.png" },

    @{ tema="Traductorado Publico en Idioma Ingles en la UMSA"; nombre_archivo="foco_grado_traductorado_ingles";
       contexto="Dura 4 anios, con modalidad presencial o virtual, y otorga el titulo de Traductor/a Publico/a en Idioma Ingles, con un titulo intermedio de Tecnico/a en Traduccion Multimedia a los dos anios. Los primeros dos anios combinan traduccion e interpretacion general; los ultimos dos se especializan en traduccion juridica, con practica de interpretacion judicial y materias de derecho privado y publico. Los egresados trabajan en organismos gubernamentales, embajadas, tribunales, agencias de traduccion, editoriales, bancos y como profesionales independientes.";
       imagen_fondo="media/placas/foco_grado_traductorado_ingles.png" },

    @{ tema="Licenciatura en Negocios Digitales en la UMSA"; nombre_archivo="foco_grado_negocios_digitales";
       contexto="Dura 4 anios en modalidad virtual y otorga el titulo de Licenciado/a en Negocios Digitales. Combina contenidos economicos, administrativos y juridicos con competencias digitales: programacion basica y tecnologia aplicada. Tambien incluye formacion en habilidades blandas como liderazgo digital y autoconocimiento. Los egresados pueden desempenarse como lider de transformacion digital, consultor en estrategia digital, product manager, especialista en marketing digital, analista de business intelligence o emprendedor digital.";
       imagen_fondo="media/placas/foco_grado_negocios_digitales.png" },

    @{ tema="Doctorado en Ciencias Juridicas - Posgrados UMSA"; nombre_archivo="posgrado_derecho";
       contexto="La UMSA ofrece el Doctorado en Ciencias Juridicas, en modalidad presencial y a distancia, acreditado por CONEAU. Tambien dicta un Posdoctorado en Ciencias Juridicas a distancia y especializaciones de posgrado en Derecho Procesal Penal. Estan dirigidos a abogados que buscan profundizar su formacion academica y de investigacion juridica, con docentes de trayectoria reconocida.";
       imagen_fondo="media/placas/posgrado_derecho.png" },

    @{ tema="Maestria en Bioetica - Posgrados UMSA"; nombre_archivo="posgrado_bioetica";
       contexto="La UMSA dicta la Maestria en Bioetica en modalidad presencial, acreditada por CONEAU. Esta pensada para profesionales de la salud, el derecho y otras disciplinas que necesiten abordar los dilemas eticos de la practica profesional y la investigacion, con docentes de trayectoria reconocida.";
       imagen_fondo="media/placas/posgrado_bioetica.png" },

    @{ tema="Maestria en Museologia Contemporanea - Posgrados UMSA"; nombre_archivo="posgrado_museologia";
       contexto="La UMSA dicta la Maestria en Museologia Contemporanea en modalidad a distancia, acreditada por CONEAU. Esta dirigida a profesionales vinculados a museos, centros culturales y patrimonio, que buscan actualizar su formacion en gestion y curaduria museistica con docentes de trayectoria reconocida.";
       imagen_fondo="media/placas/posgrado_museologia.jpeg" },

    @{ tema="Extension y Comunidad - vinculacion institucional de la UMSA"; nombre_archivo="extension_vinculacion_institucional";
       contexto="En las ultimas semanas la UMSA tuvo varias actividades de vinculacion institucional: participo del 10 aniversario de Path International Examinations el 7 de septiembre; recibio la visita del Procurador General Adjunto de la Ciudad de Buenos Aires el 1 de septiembre, en un encuentro con estudiantes y graduados de Abogacia; visito el Colegio de Traductores Publicos de la Ciudad de Buenos Aires el 27 de agosto; y recibio al Colegio de Traductores Publicos e Interpretes Regional San Isidro el 21 de agosto. Estas actividades muestran el vinculo permanente entre la universidad, el ejercicio profesional y la comunidad.";
       imagen_fondo="media/placas/extension_vinculacion_institucional.jpeg" }
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
Write-Host "Listo. Los 11 clips ya tienen su fondo real. Si el streamer esta corriendo, correr POST /api/v1/stream/reload en Swagger para que tome los cambios." -ForegroundColor Yellow
