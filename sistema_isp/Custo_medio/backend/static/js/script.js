// 1. Função para carregar os filtros dinâmicos
async function carregarFiltros() {
    try {
        const response = await fetch('http://127.0.0.1:8000/filtros/opcoes');
        if (!response.ok) throw new Error('Falha ao carregar opções');
        
        const opcoes = await response.json();
        
        // ADICIONE ESTA LINHA PARA VER O QUE CHEGOU NO CONSOLE
        console.log("Dados recebidos da API:", opcoes);

        // Se o console mostrar nomes de chaves diferentes, ajuste aqui:
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
    if (!select || !lista) return; // Segurança extra caso a lista venha nula
    
    select.innerHTML = '<option value="">Todos</option>';
    lista.forEach(item => {
        // Normalização de strings para evitar opções vazias ou 'NaN'
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
    // Captura os valores dos campos de filtro do HTML
    const campos = {
        cidade: document.getElementById('cidade')?.value,
        uf: document.getElementById('uf')?.value,
        tipo_servico: document.getElementById('tipo_servico')?.value,
        interface: document.getElementById('interface')?.value,
        ip_fixo: document.getElementById('ip_fixo')?.value,
        velocidade: document.getElementById('velocidade')?.value,
        prazo: document.getElementById('prazo')?.value
    };

    // IDs corrigidos para bater exatamente com o novo index.html unificado
    const displayMedia = document.getElementById('resultado-media');
    const displayQtd = document.getElementById('resultado-amostragem');
    const displayAviso = document.getElementById('alerta-regional');
    const textoAlerta = document.getElementById('texto-alerta');

    // CORREÇÃO: Alterado de 8000 para 8080 para bater com o FastAPI unificado
    const url = new URL('http://127.0.0.1:8000/api/custo-medio/');
    Object.keys(campos).forEach(key => {
        if (campos[key]) url.searchParams.append(key, campos[key]);
    });

    try {
        if (displayMedia) displayMedia.innerText = "Consultando...";
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('Erro na resposta do servidor');
        
        const dados = await response.json();

        // 1. Atualiza o Valor Médio na tela
        if (displayMedia) {
            const valorFormatado = (dados.custo_medio || 0).toLocaleString('pt-BR', { 
                style: 'currency', 
                currency: 'BRL' 
            });
            displayMedia.innerText = valorFormatado;
        }
        
        // 2. Atualiza a Quantidade de Amostragem
        if (displayQtd) {
            displayQtd.innerText = `${dados.quantidade_contratos || 0} contratos`;
        }

        // 3. Lógica de Alerta Regional Baseado no Bootstrap 5
        if (displayAviso && textoAlerta) {
            if (dados.tipo_resultado === "media_regional") {
                textoAlerta.innerHTML = `<strong>Aviso:</strong> Cidade sem histórico. Exibindo média regional (${campos.uf?.toUpperCase() || 'UF'}).`;
                displayAviso.classList.remove('d-none'); // Exibe o alerta
            } else if (dados.quantidade_contratos === 0 || dados.custo_medio === 0) {
                textoAlerta.innerHTML = "<strong>Nenhum contrato</strong> encontrado para estes filtros cadastrados.";
                displayAviso.classList.remove('d-none'); // Exibe o alerta
            } else {
                displayAviso.classList.add('d-none'); // Oculta o alerta se deu tudo certo
            }
        }

    } catch (error) {
        console.error('Erro:', error);
        // CORREÇÃO: Ajustada mensagem de alerta para apontar para a porta 8080
        alert('Erro ao conectar com o servidor da API. Verifique se o FastAPI está rodando na porta 8000.')
        if (displayMedia) displayMedia.innerText = "R$ 0,00";
    }
}

// 3. Processamento de Planilha em Lote
async function subirPlanilha() {
    // ID corrigido para o padrão com hífen do HTML
    const fileInput = document.getElementById('arquivo-csv');
    if (!fileInput || fileInput.files.length === 0) {
        alert("Por favor, selecione um arquivo CSV primeiro.");
        return;
    }

    // Seletor ajustado para o ID correto do novo botão
    const btn = document.getElementById('btn-processar-lote');
    const originalText = btn.innerHTML;
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>PROCESSANDO...';
        btn.disabled = true;

        // CORREÇÃO: Alterado de 8000 para 8080 para bater com o FastAPI unificado
        const response = await fetch('http://127.0.0.1:8000/contratos/processar-planilha', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Erro ao processar arquivo');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "resultado_custos.csv"; // Nome limpo e profissional
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url); // Limpa o buffer de memória
        
        alert("Sucesso! A planilha com os custos calculados foi baixada automaticamente.");
    } catch (error) {
        console.error(error);
        alert("Falha no processamento em lote. Certifique-se de que o CSV usa separador ponto e vírgula e possui as colunas obrigatórias.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Inicialização Unificada e Atribuição de Eventos
document.addEventListener('DOMContentLoaded', () => {
    // Carrega os selects assim que a página abrir
    carregarFiltros();

    // Atribui a função de calcular ao clique do botão correspondente
    const btnCalcular = document.getElementById('btn-calcular');
    if (btnCalcular) {
        btnCalcular.addEventListener('click', buscarMedia);
    }

    // Atribui a função de lote ao clique do botão de planilha
    const btnLote = document.getElementById('btn-processar-lote');
    if (btnLote) {
        btnLote.addEventListener('click', subirPlanilha);
    }
});

