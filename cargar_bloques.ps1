$clips = @(
    @{ tema="Carrera de Abogacia en la UMSA"; nombre_archivo="foco_grado_abogacia";
       contexto="Es una carrera de 5 anios que otorga el titulo de Abogado/a. Modalidad presencial o virtual. Prepara para patrocinar y representar a las partes en procedimientos judiciales y administrativos, ejercer funciones jurisdiccionales, emitir dictamenes juridicos y actuar como sindico en sociedades. El plan de estudios tiene fuerte formacion practica: talleres de litigacion, redaccion de escritos judiciales, analisis jurisprudencial y clinicas legales que simulan el ejercicio profesional real, ademas de incorporar herramientas de inteligencia artificial y gestion documental." },

    @{ tema="Carrera de Contador Publico en la UMSA"; nombre_archivo="foco_grado_contador_publico";
       contexto="Dura 4 anios en modalidad presencial y otorga el titulo de Contador Publico. Forma profesionales para el asesoramiento, la planificacion y el control de la actividad contable, tributaria, societaria y de gestion economica y financiera en organizaciones publicas y privadas. Combina contabilidad avanzada con derecho economico y legislacion laboral, incluye materias de sistemas de informacion y auditoria de sistemas computarizados, y ofrece dos modulos de practica profesional supervisada en el cuarto anio." },

    @{ tema="Licenciatura en Artes Visuales en la UMSA"; nombre_archivo="foco_grado_artes_visuales";
       contexto="Dura 4 anios en modalidad presencial y otorga el titulo de Licenciado/a en Artes Visuales. Ofrece una formacion integral en cuatro especialidades: pintura, grabado, escultura y nuevos medios. Los egresados trabajan en producciones artisticas individuales y colectivas, museos, galerias y centros culturales, cine, animacion, teatro, escenografia, disenio grafico y docencia. El plan incluye investigacion visual y laboratorios de imagen, con posibilidad de especializarse en fotografia, narrativa audiovisual y arte multimedial." },

    @{ tema="Licenciatura en Psicologia en la UMSA"; nombre_archivo="foco_grado_psicologia";
       contexto="Dura 4 anios y medio, incluyendo practicas profesionales supervisadas en el tramo final, y otorga el titulo de Licenciado/a en Psicologia. Se organiza en cinco areas: clinica, laboral, forense, educacional y comunitaria. Los egresados trabajan en hospitales y centros terapeuticos, consultorios privados, recursos humanos, el ambito educativo, organismos gubernamentales y ONGs. El plan incluye materias como psicodiagnostico, psicoterapias breves y terapia sistemica, y fomenta la participacion en proyectos de investigacion desde los primeros anios." },

    @{ tema="Traductorado Publico en Idioma Ingles en la UMSA"; nombre_archivo="foco_grado_traductorado_ingles";
       contexto="Dura 4 anios, con modalidad presencial o virtual, y otorga el titulo de Traductor/a Publico/a en Idioma Ingles, con un titulo intermedio de Tecnico/a en Traduccion Multimedia a los dos anios. Los primeros dos anios combinan traduccion e interpretacion general; los ultimos dos se especializan en traduccion juridica, con practica de interpretacion judicial y materias de derecho privado y publico. Los egresados trabajan en organismos gubernamentales, embajadas, tribunales, agencias de traduccion, editoriales, bancos y como profesionales independientes." },

    @{ tema="Licenciatura en Negocios Digitales en la UMSA"; nombre_archivo="foco_grado_negocios_digitales";
       contexto="Dura 4 anios en modalidad virtual y otorga el titulo de Licenciado/a en Negocios Digitales. Combina contenidos economicos, administrativos y juridicos con competencias digitales: programacion basica y tecnologia aplicada. Tambien incluye formacion en habilidades blandas como liderazgo digital y autoconocimiento. Los egresados pueden desempenarse como lider de transformacion digital, consultor en estrategia digital, product manager, especialista en marketing digital, analista de business intelligence o emprendedor digital." },

    @{ tema="Doctorado en Ciencias Juridicas - Posgrados UMSA"; nombre_archivo="posgrado_derecho";
       contexto="La UMSA ofrece el Doctorado en Ciencias Juridicas, en modalidad presencial y a distancia, acreditado por CONEAU. Tambien dicta un Posdoctorado en Ciencias Juridicas a distancia y especializaciones de posgrado en Derecho Procesal Penal. Estan dirigidos a abogados que buscan profundizar su formacion academica y de investigacion juridica, con docentes de trayectoria reconocida." },

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
