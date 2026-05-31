// meu-app-geo - Lógica do Mapa e Dashboard Interativo Estendido

document.addEventListener("DOMContentLoaded", () => {
    
    // ----------------------------------------------------
    // 1. Inicialização do Mapa Leaflet Principal
    // ----------------------------------------------------
    const map = L.map("map-container").setView([-18.5, -46.5], 5);
    
    // Camada de Tiles Escuros (CartoDB Dark Matter) - Visual Premium Dark
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
    
    let markerLayerGroup = L.layerGroup().addTo(map);

    // ----------------------------------------------------
    // 2. Elementos do DOM
    // ----------------------------------------------------
    const form = document.getElementById("converter-form");
    const sourceTypeSelect = document.getElementById("source-type");
    const targetTypeSelect = document.getElementById("target-type");
    const sourceDatumSelect = document.getElementById("source-datum");
    const targetDatumSelect = document.getElementById("target-datum");
    
    const sourceUtmContainer = document.getElementById("source-utm-container");
    const targetUtmContainer = document.getElementById("target-utm-container");
    const localParamsContainer = document.getElementById("local-params-container");
    
    // File inputs
    const fileDropZone = document.getElementById("file-drop-zone");
    const fileInput = document.getElementById("file-input");
    const fileIndicator = document.getElementById("file-indicator");
    const selectedFileName = document.getElementById("selected-file-name");
    const removeFileBtn = document.getElementById("remove-file-btn");
    
    // View States
    const idlePlaceholder = document.getElementById("idle-placeholder-card");
    const loadingCard = document.getElementById("loading-card");
    const resultsMetaPanel = document.getElementById("results-meta-panel");
    const resultsTablePanel = document.getElementById("results-table-panel");
    
    // Results
    const statTotalPoints = document.getElementById("stat-total-points");
    const statTime = document.getElementById("stat-time");
    const statDelimiter = document.getElementById("stat-delimiter");
    const statAlerts = document.getElementById("stat-alerts");
    const statAlertCard = document.getElementById("stat-alert-card");
    
    const downloadCsvBtn = document.getElementById("download-csv-btn");
    const downloadKmlBtn = document.getElementById("download-kml-btn");
    const resultsTableBody = document.getElementById("results-table-body");

    // Modal Origin Elements
    const mapPinBtn = document.getElementById("map-pin-btn");
    const originModal = document.getElementById("origin-modal");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const confirmOriginBtn = document.getElementById("confirm-origin-btn");
    const modalCoordsDisplay = document.getElementById("modal-coords-display");
    
    // Toast Detection Elements
    const detectToast = document.getElementById("detect-toast");
    const toastYesBtn = document.getElementById("toast-yes-btn");
    const toastNoBtn = document.getElementById("toast-no-btn");

    let modalMap = null;
    let modalClickMarker = null;
    let selectedOriginData = null; // Guarda x, y, fuso temporários da modal

    // ----------------------------------------------------
    // 3. Controle de Exibição Dinâmica dos Painéis
    // ----------------------------------------------------
    function toggleGeodeticPanels() {
        const sourceType = sourceTypeSelect.value;
        const targetType = targetTypeSelect.value;
        
        // 3.1 Painel UTM de Entrada
        if (sourceType === "utm") {
            sourceUtmContainer.style.display = "block";
            document.getElementById("source-utm-zone").setAttribute("required", "true");
        } else {
            sourceUtmContainer.style.display = "none";
            document.getElementById("source-utm-zone").removeAttribute("required");
        }
        
        // 3.2 Painel UTM de Saída
        if (targetType === "utm") {
            targetUtmContainer.style.display = "block";
            document.getElementById("target-utm-zone").setAttribute("required", "true");
        } else {
            targetUtmContainer.style.display = "none";
            document.getElementById("target-utm-zone").removeAttribute("required");
        }
        
        // 3.3 Painel de Topografia Local (Exibe se qualquer um for 'local')
        if (sourceType === "local" || targetType === "local") {
            localParamsContainer.style.display = "block";
            document.getElementById("local-origin-x").setAttribute("required", "true");
            document.getElementById("local-origin-y").setAttribute("required", "true");
        } else {
            localParamsContainer.style.display = "none";
            document.getElementById("local-origin-x").removeAttribute("required");
            document.getElementById("local-origin-y").removeAttribute("required");
        }
    }

    sourceTypeSelect.addEventListener("change", toggleGeodeticPanels);
    targetTypeSelect.addEventListener("change", toggleGeodeticPanels);

    // ----------------------------------------------------
    // 4. Modal: "Definir Origem no Mapa"
    // ----------------------------------------------------
    mapPinBtn.addEventListener("click", () => {
        originModal.style.display = "flex";
        
        // Inicializar mapa da modal apenas uma vez
        if (!modalMap) {
            setTimeout(() => {
                modalMap = L.map("modal-map-container").setView([-18.5, -46.5], 4);
                
                L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
                    attribution: '&copy; CARTO &copy; OpenStreetMap',
                    maxZoom: 18
                }).addTo(modalMap);
                
                // Evento de clique no mapa modal
                modalMap.on("click", (e) => {
                    const lat = e.latlng.lat;
                    const lon = e.latlng.lng;
                    
                    // Colocar ou mover marcador
                    if (modalClickMarker) {
                        modalClickMarker.setLatLng(e.latlng);
                    } else {
                        modalClickMarker = L.marker(e.latlng).addTo(modalMap);
                    }
                    
                    // Lógica de Autopreenchimento do Datum no Brasil (Lat entre 5°N e 34°S)
                    if (lat >= -34.0 && lat <= 5.0 && lon >= -74.0 && lon <= -34.0) {
                        sourceDatumSelect.value = "SIRGAS_2000";
                        targetDatumSelect.value = "SIRGAS_2000";
                    }
                    
                    // Consultar back-end para converter Lat/Lon para UTM no ponto exato
                    modalCoordsDisplay.textContent = "Convertendo ponto...";
                    confirmOriginBtn.disabled = true;
                    
                    fetch(`/convert_point?lat=${lat}&lon=${lon}`)
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                selectedOriginData = data;
                                modalCoordsDisplay.textContent = `UTM: E ${data.x.toLocaleString()} m | N ${data.y.toLocaleString()} m | Fuso ${data.zone}S`;
                                confirmOriginBtn.disabled = false;
                            } else {
                                modalCoordsDisplay.textContent = "Erro ao converter ponto.";
                            }
                        })
                        .catch(() => {
                            modalCoordsDisplay.textContent = "Erro na conexão com o servidor.";
                        });
                });
            }, 200);
        } else {
            // Se já inicializado, recalcular tamanho para evitar cinza no Leaflet
            setTimeout(() => {
                modalMap.invalidateSize();
            }, 200);
        }
    });
    
    closeModalBtn.addEventListener("click", () => {
        originModal.style.display = "none";
    });
    
    confirmOriginBtn.addEventListener("click", () => {
        if (selectedOriginData) {
            document.getElementById("local-origin-x").value = selectedOriginData.x;
            document.getElementById("local-origin-y").value = selectedOriginData.y;
            document.getElementById("local-origin-zone").value = selectedOriginData.zone;
            originModal.style.display = "none";
        }
    });

    // ----------------------------------------------------
    // 5. Mecanismo de Upload e Auto-Detecção de UTM
    // ----------------------------------------------------
    fileDropZone.addEventListener("click", () => fileInput.click());
    
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            handleFileSelection(file);
            autoDetectFileCoordinates(file);
        }
    });

    fileDropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        fileDropZone.classList.add("dragover");
    });

    fileDropZone.addEventListener("dragleave", () => {
        fileDropZone.classList.remove("dragover");
    });

    fileDropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        fileDropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            const file = e.dataTransfer.files[0];
            handleFileSelection(file);
            autoDetectFileCoordinates(file);
        }
    });

    function handleFileSelection(file) {
        selectedFileName.textContent = file.name;
        fileDropZone.style.display = "none";
        fileIndicator.style.display = "flex";
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.value = "";
        fileIndicator.style.display = "none";
        fileDropZone.style.display = "block";
        detectToast.style.display = "none"; // Fecha o balão se remover arquivo
    });

    // Função de Auto-Detecção inteligente de UTM
    function autoDetectFileCoordinates(file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const text = e.target.result;
            const lines = text.split(/\r?\n/);
            
            // Tenta procurar coordenadas nas primeiras 5 linhas
            for (let i = 0; i < Math.min(lines.length, 5); i++) {
                const line = lines[i].trim();
                if (!line) continue;
                
                // Encontra todos os números (com sinais opcionais e pontos/vírgulas)
                const numbers = line.replace(/,/g, '.').match(/[-+]?(?:\d*\.\d+|\d+)/g);
                if (numbers && numbers.length >= 2) {
                    // Verifica se uma das coordenadas tem 6 dígitos (Easting) e a outra 7 dígitos (Northing)
                    const hasEasting = numbers.some(num => {
                        const val = Math.abs(parseFloat(num));
                        return val >= 100000 && val < 999999;
                    });
                    const hasNorthing = numbers.some(num => {
                        const val = Math.abs(parseFloat(num));
                        return val >= 1000000 && val < 9999999;
                    });
                    
                    if (hasEasting && hasNorthing) {
                        // Exibir balão toast animado de autodetecção
                        detectToast.style.display = "flex";
                        break;
                    }
                }
            }
        };
        // Lê apenas os primeiros 4KB do arquivo para excelente performance
        reader.readAsText(file.slice(0, 4096));
    }

    // Ações do Balão Toast de Autodetecção
    toastYesBtn.addEventListener("click", () => {
        sourceTypeSelect.value = "utm";
        sourceDatumSelect.value = "SIRGAS_2000";
        document.getElementById("source-utm-hemi").value = "S";
        // Tenta pré-configurar fuso comum 23S
        document.getElementById("source-utm-zone").value = "23";
        toggleGeodeticPanels();
        
        // Feedback visual e fecha balão
        detectToast.style.animation = "fadeOut 0.3s ease forwards";
        setTimeout(() => {
            detectToast.style.display = "none";
            detectToast.style.animation = "";
        }, 300);
    });

    toastNoBtn.addEventListener("click", () => {
        detectToast.style.animation = "fadeOut 0.3s ease forwards";
        setTimeout(() => {
            detectToast.style.display = "none";
            detectToast.style.animation = "";
        }, 300);
    });

    // ----------------------------------------------------
    // 6. Envio do Formulário AJAX
    // ----------------------------------------------------
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        
        if (!fileInput.files || fileInput.files.length === 0) {
            alert("Por favor, selecione um arquivo de coordenadas primeiro.");
            return;
        }

        idlePlaceholder.style.display = "none";
        resultsMetaPanel.style.display = "none";
        resultsTablePanel.style.display = "none";
        loadingCard.style.display = "block";
        
        markerLayerGroup.clearLayers();
        
        const formData = new FormData(form);
        
        fetch("/convert", {
            method: "POST",
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            loadingCard.style.display = "none";
            
            if (data.success) {
                resultsMetaPanel.style.display = "block";
                resultsTablePanel.style.display = "block";
                
                statTotalPoints.textContent = data.total_points.toLocaleString();
                statTime.textContent = `${(data.stats.time_s * 1000).toFixed(0)} ms`;
                statDelimiter.textContent = data.stats.delimiter;
                statAlerts.textContent = data.alert_count;
                
                if (data.has_precision_alerts) {
                    statAlertCard.classList.add("failed-precision");
                } else {
                    statAlertCard.classList.remove("failed-precision");
                }
                
                downloadCsvBtn.setAttribute("href", data.download_csv_url);
                downloadKmlBtn.setAttribute("href", data.download_kml_url);
                
                renderResultsTable(data.points, data.stats.columns);
                plotPointsOnMap(data.points, data.stats.columns);
            }
        })
        .catch(err => {
            loadingCard.style.display = "none";
            idlePlaceholder.style.display = "block";
            alert(err.message || "Ocorreu um erro ao processar o arquivo.");
            console.error("Erro:", err);
        });
    });

    // ----------------------------------------------------
    // 7. Funções de Renderização Dinâmicas
    // ----------------------------------------------------
    function renderResultsTable(points, columns) {
        resultsTableBody.innerHTML = "";
        
        points.forEach(pt => {
            const tr = document.createElement("tr");
            
            if (pt.PRECISION_ALERT) {
                tr.classList.add("failed-precision-row");
            }
            
            const idVal = pt[columns.id] !== undefined ? pt[columns.id] : "";
            const origX = pt[columns.x];
            const origY = pt[columns.y];
            
            const formatDec = (val, max = 3) => {
                if (typeof val === 'string') return val;
                const sourceType = sourceTypeSelect.value;
                if (Math.abs(val) < 180 && (sourceType === 'geo' || sourceType === 'gms')) {
                    return val.toFixed(8);
                }
                return val.toFixed(max);
            };
            
            const targetType = targetTypeSelect.value;
            let convXStr = "";
            let convYStr = "";
            
            if (targetType === "gms") {
                convXStr = pt.CONVERTED_X_TXT || "";
                convYStr = pt.CONVERTED_Y_TXT || "";
            } else if (targetType === "MGRS") {
                convXStr = pt.CONVERTED_MGRS || "";
                convYStr = "-";
            } else {
                const decPlaces = (targetType === 'geo') ? 8 : 3;
                convXStr = pt.CONVERTED_X !== undefined ? Number(pt.CONVERTED_X).toFixed(decPlaces) : "";
                convYStr = pt.CONVERTED_Y !== undefined ? Number(pt.CONVERTED_Y).toFixed(decPlaces) : "";
            }
            
            const zVal = pt[columns.z] !== undefined ? Number(pt[columns.z]) : 0;
            const devVal = pt.PRECISION_DEV_M !== undefined ? Number(pt.PRECISION_DEV_M) : 0;
            
            const statusBadge = pt.PRECISION_ALERT 
                ? '<span class="status-badge status-alert">> 2cm</span>' 
                : '<span class="status-badge status-ok">OK</span>';

            tr.innerHTML = `
                <td><b>${idVal}</b></td>
                <td>${formatDec(origX)}</td>
                <td>${formatDec(origY)}</td>
                <td style="font-family: monospace;">${convXStr}</td>
                <td style="font-family: monospace;">${convYStr}</td>
                <td>${zVal.toFixed(3)} m</td>
                <td style="font-family: monospace;">${devVal.toFixed(6)} m</td>
                <td>${statusBadge}</td>
            `;
            
            resultsTableBody.appendChild(tr);
        });
    }

    function plotPointsOnMap(points, columns) {
        const bounds = L.latLngBounds();
        
        points.forEach(pt => {
            const lat = pt.MAP_LAT;
            const lon = pt.MAP_LON;
            
            if (lat === undefined || lon === undefined || isNaN(lat) || isNaN(lon)) {
                return;
            }
            
            const latLng = L.latLng(lat, lon);
            bounds.extend(latLng);
            
            const isAlert = pt.PRECISION_ALERT;
            
            const markerOptions = {
                radius: isAlert ? 7 : 5,
                fillColor: isAlert ? "#ff1744" : "#00e676",
                color: "#ffffff",
                weight: isAlert ? 1.5 : 1,
                opacity: 1,
                fillOpacity: 0.85
            };
            
            const marker = L.circleMarker(latLng, markerOptions);
            
            const idVal = pt[columns.id] !== undefined ? pt[columns.id] : "";
            const origX = pt[columns.x];
            const origY = pt[columns.y];
            
            const targetType = targetTypeSelect.value;
            let convXStr = "";
            let convYStr = "";
            
            if (targetType === "gms") {
                convXStr = pt.CONVERTED_X_TXT || "";
                convYStr = pt.CONVERTED_Y_TXT || "";
            } else if (targetType === "MGRS") {
                convXStr = pt.CONVERTED_MGRS || "";
                convYStr = "-";
            } else {
                convXStr = pt.CONVERTED_X !== undefined ? pt.CONVERTED_X : "";
                convYStr = pt.CONVERTED_Y !== undefined ? pt.CONVERTED_Y : "";
            }
            
            const zVal = pt[columns.z] !== undefined ? pt[columns.z] : 0;
            const devVal = pt.PRECISION_DEV_M !== undefined ? pt.PRECISION_DEV_M : 0;
            
            const formatDecPopup = (val) => {
                return typeof val === 'number' ? val.toFixed(5) : val;
            };

            const popupContent = `
                <div style="font-family: 'Inter', sans-serif; font-size: 11.5px; line-height: 1.5; min-width: 210px;">
                    <h4 style="font-family: 'Outfit', sans-serif; font-size: 13px; font-weight: 700; color: #00e5ff; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px;">Ponto: ${idVal}</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="color:#9ca3af; padding: 2px 0;">Origem X/Lon:</td><td style="text-align: right; font-weight: 500;">${formatDecPopup(origX)}</td></tr>
                        <tr><td style="color:#9ca3af; padding: 2px 0;">Origem Y/Lat:</td><td style="text-align: right; font-weight: 500;">${formatDecPopup(origY)}</td></tr>
                        <tr style="border-bottom: 1px dashed rgba(255,255,255,0.08);"><td colspan="2"></td></tr>
                        <tr><td style="color:#9ca3af; padding: 2px 0;">Convertido X:</td><td style="text-align: right; font-weight: 500; font-family: monospace;">${typeof convXStr === 'number' ? convXStr.toFixed(4) : convXStr}</td></tr>
                        ${targetType !== 'MGRS' ? `<tr><td style="color:#9ca3af; padding: 2px 0;">Convertido Y:</td><td style="text-align: right; font-weight: 500; font-family: monospace;">${typeof convYStr === 'number' ? convYStr.toFixed(4) : convYStr}</td></tr>` : ''}
                        <tr><td style="color:#9ca3af; padding: 2px 0;">Cota Alt. Z:</td><td style="text-align: right; font-weight: 500;">${Number(zVal).toFixed(3)} m</td></tr>
                        <tr style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 4px;"><td style="color:#9ca3af; padding: 4px 0 2px 0;">Desvio (Inversa):</td><td style="text-align: right; font-weight: 700; color: ${isAlert ? '#ff1744' : '#00e676'}; padding-top: 4px;">${devVal.toFixed(6)} m</td></tr>
                        <tr><td style="color:#9ca3af; padding: 2px 0;">Status:</td><td style="text-align: right; font-weight: 700; color: ${isAlert ? '#ff1744' : '#00e676'};">${isAlert ? 'ALERTA > 2cm' : 'OK'}</td></tr>
                    </table>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            markerLayerGroup.addLayer(marker);
        });
        
        if (bounds.isValid()) {
            map.fitBounds(bounds, {
                padding: [40, 40],
                maxZoom: 16
            });
        }
    }
});
