// 1. Função para carregar os filtros dinâmicos
async function carregarFiltros() {
    try {
        const response = await fetch('http://127.0.0.1:8000/filtros/opcoes');
        if (!response.ok) throw new Error('Falha ao carregar opções');
        
        const opcoes = await response.json();
        
        console.log("Dados recebidos da API:", opcoes);

        preencherSelect('tipo_servico', opcoes.servicos || []);
        preencherSelect('interface', opcoes.interfaces || []);
        preencherSelect('ip_fixo', opcoes.ips || []);
        
    } catch (e) {
        console.error("Erro ao carregar filtros:", e);
    }
}

// Função auxiliar para montar as opções
function preencherSelect(id, lista) {
    const select = document.getElementById(id);
    if (!select || !lista) return; 
    
    select.innerHTML = '<option value="">Todos</option>';
    lista.forEach(item => {
        if (item && item.toString().toUpperCase() !== 'NAN' && item.toString().toUpperCase() !== 'NÃO INFORMADO') {
            const option = document.createElement('option');
            option.value = item;
            option.textContent = item;
            select.appendChild(option);
        }
    });
}

// 2. Busca Individual com Lógica de Média Regional
async function buscarMedia() {
    // IMPORTANTE: As chaves aqui (servico, capacidade, vigencia) 
    // DEVEM ser idênticas ao que está no seu if request.GET.get('...') no Python.
    const campos = {
        cidade: document.getElementById('cidade')?.value || '',
        uf: document.getElementById('uf')?.value || '',
        servico: document.getElementById('tipo_servico')?.value || '', // Mudou de tipo_servico para servico
        interface: document.getElementById('interface')?.value || '',
        ip_fixo: document.getElementById('ip_fixo')?.value || '',
        capacidade: document.getElementById('velocidade')?.value || '', // Mudou de velocidade para capacidade
        vigencia: document.getElementById('prazo')?.value || ''          // Mudou de prazo para vigencia
    };

    const displayMedia = document.getElementById('resultado-media');
    const displayQtd = document.getElementById('resultado-amostragem');
    const displayAviso = document.getElementById('alerta-regional');
    const textoAlerta = document.getElementById('texto-alerta');

    // URL normalizada para porta 8000
    const url = new URL('http://127.0.0.1:8000/api/custo-medio/');
    Object.keys(campos).forEach(key => {
        if (campos[key]) url.searchParams.append(key, campos[key]);
    });

    try {
        if (displayMedia) displayMedia.innerText = "Consultando...";
        
        const response = await fetch(url, { method: 'GET', headers: { 'Accept': 'application/json' } });
        if (!response.ok) throw new Error('Erro na resposta do servidor');
        
        const dados = await response.json();

        // 1. Atualiza o Valor Médio
        if (displayMedia) {
            const valorFormatado = (dados.custo_medio || 0).toLocaleString('pt-BR', { 
                style: 'currency', 
                currency: 'BRL' 
            });
            displayMedia.innerText = valorFormatado;
        }
        
        // 2. Atualiza a Amostragem
        if (displayQtd) {
            displayQtd.innerText = `${dados.quantidade_contratos || 0} contratos`;
        }

        // 3. Lógica de Alerta
        if (displayAviso && textoAlerta) {
            if (dados.tipo_resultado === "media_regional") {
                textoAlerta.innerHTML = `<strong>Aviso:</strong> Cidade sem histórico. Exibindo média regional (${campos.uf?.toUpperCase() || 'UF'}).`;
                displayAviso.classList.remove('d-none');
            } else if (dados.quantidade_contratos === 0 || dados.custo_medio === 0) {
                textoAlerta.innerHTML = "<strong>Nenhum contrato</strong> encontrado para estes filtros.";
                displayAviso.classList.remove('d-none');
            } else {
                displayAviso.classList.add('d-none');
            }
        }

    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao conectar com o servidor da API. Verifique se o FastAPI está rodando na porta 8000.')
        if (displayMedia) displayMedia.innerText = "R$ 0,00";
    }
}

// 3. Processamento de Planilha em Lote
async function subirPlanilha() {
    const fileInput = document.getElementById('arquivo-csv');
    if (!fileInput || fileInput.files.length === 0) {
        alert("Por favor, selecione um arquivo CSV primeiro.");
        return;
    }

    const btn = document.getElementById('btn-processar-lote');
    const originalText = btn.innerHTML;
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>PROCESSANDO...';
        btn.disabled = true;

        // URL normalizada para porta 8000
        const response = await fetch('http://127.0.0.1:8000/contratos/processar-planilha', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Erro ao processar arquivo');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "resultado_custos.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        
        alert("Sucesso! A planilha com os custos calculados foi baixada.");
    } catch (error) {
        console.error(error);
        alert("Falha no processamento em lote. Verifique se o arquivo está correto e se o servidor na porta 8000 está ativo.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    carregarFiltros();

    const btnCalcular = document.getElementById('btn-calcular');
    if (btnCalcular) btnCalcular.addEventListener('click', buscarMedia);

    const btnLote = document.getElementById('btn-processar-lote');
    if (btnLote) btnLote.addEventListener('click', subirPlanilha);
});