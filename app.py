import streamlit as st
import json
import os
import uuid
import requests
import base64
import datetime
import time

st.set_page_config(page_title="Minhas Viagens", page_icon="✈️", layout="wide")

ARQUIVO_DADOS = 'viagens.json'

# --- 1. FUNÇÕES DE SUPORTE E API ---
def formatar_moeda(valor):
    """Transforma 10000.5 em 10.000,50 no padrão BR"""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_inteiro(valor):
    """Transforma milhas de 10000 para 10.000"""
    texto = f"{valor:,}"
    return texto.replace(",", ".")

@st.cache_data(ttl=3600)
def buscar_cotacao_api(moeda):
    if moeda == "BRL": return 1.0
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{moeda}"
        res = requests.get(url, timeout=3)
        return float(res.json()['rates'].get('BRL', 1.0))
    except:
        return 1.0

# --- GATILHOS DE ATUALIZAÇÃO (A Mágica da Cotação!) ---
def on_moeda_change_rot():
    """Força a cotação do Roteiro a atualizar na mesma hora que a moeda muda"""
    rk = st.session_state.rot_key
    if f"rm_{rk}" in st.session_state:
        moeda_selecionada = st.session_state[f"rm_{rk}"]
        st.session_state[f"rc_{rk}"] = buscar_cotacao_api(moeda_selecionada)

def on_moeda_change_fin():
    """Força a cotação do Financeiro a atualizar na mesma hora que a moeda muda"""
    fk = st.session_state.fin_key
    if f"fm_{fk}" in st.session_state:
        moeda_selecionada = st.session_state[f"fm_{fk}"]
        st.session_state[f"fct_{fk}"] = buscar_cotacao_api(moeda_selecionada)

def simular_api_voos(codigo):
    mock = {
        "LA750": {"cia": "LATAM Airlines", "origem": "GRU - São Paulo", "destino": "SCL - Santiago", "saida": "10:30", "chegada": "14:45"},
        "G3123": {"cia": "Gol Linhas Aéreas", "origem": "CGH - São Paulo", "destino": "SDU - Rio de Janeiro", "saida": "08:00", "chegada": "09:00"}
    }
    return mock.get(codigo.upper().strip(), None)

def converter_imagem_base64(arquivo):
    if arquivo is not None:
        return f"data:{arquivo.type};base64,{base64.b64encode(arquivo.getvalue()).decode()}"
    return ""

def calcular_resumo_financeiro(viagem):
    total_geral = 0.0
    total_pago = 0.0
    
    for d in viagem.get('despesas', []):
        val_brl = d.get('valor', 0) * d.get('cotacao', 1.0)
        total_geral += val_brl
        if d.get('pago'): total_pago += val_brl
            
    for r in viagem.get('roteiro', []):
        custo_atividade = (r.get('custo_passeio', 0) + r.get('custo_ingresso', 0)) * r.get('cotacao', 1.0)
        total_geral += custo_atividade
        if r.get('pago'): total_pago += custo_atividade
            
    for v in viagem.get('voos', []):
        custo_voo = v.get('custo_brl', 0) + v.get('taxas_brl', 0)
        total_geral += custo_voo
        if v.get('status') == 'Comprado': total_pago += custo_voo
            
    for c in viagem.get('carros', []):
        custo_carro = c.get('custo_brl', 0)
        total_geral += custo_carro
        if c.get('status') == 'Alugado' or c.get('pago'): total_pago += custo_carro
            
    return total_geral, total_pago, total_geral - total_pago

# --- 2. PERSISTÊNCIA DE DADOS ---
def carregar_viagens():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def salvar_viagens(dados):
    with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if 'viagens' not in st.session_state: st.session_state.viagens = carregar_viagens()
if 'edit_id' not in st.session_state: st.session_state.edit_id = None
if 'edit_tab' not in st.session_state: st.session_state.edit_tab = None
if 'voo_temp' not in st.session_state: st.session_state.voo_temp = {}
if 'rot_key' not in st.session_state: st.session_state.rot_key = 0
if 'fin_key' not in st.session_state: st.session_state.fin_key = 0

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title("✈️ Minhas Viagens")
    if st.button("➕ Nova Viagem", use_container_width=True):
        st.session_state.viagens.append({
            "id": str(uuid.uuid4()), "titulo": "Nova Viagem (Edite o Título)", "paises": "",
            "inicio": "", "fim": "", "status": "Em planejamento", "coverImage": "",
            "despesas": [], "tarefas": [], "voos": [], "carros": [], "roteiro": []
        })
        salvar_viagens(st.session_state.viagens)
        st.rerun()

    st.divider()
    
    if not st.session_state.viagens:
        st.info("Sua lista está vazia. Crie uma nova viagem acima!")
        viagem_atual = None
    else:
        titulos = [v['titulo'] for v in st.session_state.viagens]
        viagem_selecionada = st.radio("Selecione para organizar:", titulos)
        viagem_atual = next((v for v in st.session_state.viagens if v['titulo'] == viagem_selecionada), None)

# --- 4. ÁREA PRINCIPAL ---
if viagem_atual:
    capa = viagem_atual.get('coverImage') or "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1000&q=80"
    st.markdown(f"""
        <div style="width: 100%; height: 220px; background-image: url('{capa}');
            background-size: cover; background-position: center;
            border-radius: 12px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        </div>
    """, unsafe_allow_html=True)
        
    st.title(f"📍 {viagem_atual['titulo']}")
    
    t_geral, t_pago, t_falta = calcular_resumo_financeiro(viagem_atual)
    qtd_dias = 0
    if viagem_atual.get('inicio') and viagem_atual.get('fim'):
        try:
            d_ini = datetime.datetime.strptime(viagem_atual['inicio'], "%Y-%m-%d")
            d_fim = datetime.datetime.strptime(viagem_atual['fim'], "%Y-%m-%d")
            qtd_dias = (d_fim - d_ini).days
        except: pass

    abas = st.tabs(["📊 Visão Geral", "🗺️ Roteiro", "💰 Financeiro", "✈️ Voos", "🚗 Carros", "✅ Checklist"])
    
    # ==========================================
    # ABA 1: VISÃO GERAL 
    # ==========================================
    with abas[0]:
        st.subheader("Resumo da Viagem")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Custo Total Estimado", f"R$ {formatar_moeda(t_geral)}")
        m2.metric("Já Pago", f"R$ {formatar_moeda(t_pago)}", delta="✅ Garantido", delta_color="off")
        m3.metric("Falta Pagar", f"R$ {formatar_moeda(t_falta)}", delta="⚠️ Pendente", delta_color="off")
        m4.metric("Duração", f"{qtd_dias} dias" if qtd_dias > 0 else "--")
        
        st.divider()
        
        with st.expander("✏️ Editar Configurações Básicas ou Excluir Viagem", expanded=False):
            c_titulo, c_capa = st.columns(2)
            novo_titulo = c_titulo.text_input("Título", value=viagem_atual.get('titulo', ''))
            nova_capa = c_capa.text_input("URL da Foto de Capa", value=viagem_atual.get('coverImage', ''))
            
            novos_paises = st.text_input("Destinos (Ex: Brasil, Chile)", value=viagem_atual.get('paises', ''))
            
            c_ini, c_fim, c_stat = st.columns(3)
            
            try: data_ini_val = datetime.datetime.strptime(viagem_atual.get('inicio', ''), "%Y-%m-%d").date()
            except: data_ini_val = datetime.date.today()
                
            try: data_fim_val = datetime.datetime.strptime(viagem_atual.get('fim', ''), "%Y-%m-%d").date()
            except: data_fim_val = datetime.date.today()
            
            nova_data_inicio = c_ini.date_input("Data Início", value=data_ini_val, format="DD/MM/YYYY")
            nova_data_fim = c_fim.date_input("Data Fim", value=data_fim_val, format="DD/MM/YYYY")
            
            lista_status = ["Em planejamento", "Quero Visitar", "Reservado", "Concluído"]
            status_atual = viagem_atual.get('status', 'Em planejamento')
            idx_status = lista_status.index(status_atual) if status_atual in lista_status else 0
            novo_status = c_stat.selectbox("Status", lista_status, index=idx_status)
            
            if st.button("Salvar Configurações"):
                viagem_atual.update({
                    "titulo": novo_titulo, "paises": novos_paises, 
                    "inicio": str(nova_data_inicio), "fim": str(nova_data_fim), 
                    "status": novo_status, "coverImage": nova_capa
                })
                salvar_viagens(st.session_state.viagens)
                st.rerun()

            st.divider()
            
            st.markdown("**Zona de Perigo**")
            st.warning("Cuidado: Esta ação apagará permanentemente a viagem, roteiros, finanças e reservas associadas.")
            confirmar_exclusao = st.checkbox("Eu entendo e quero excluir esta viagem.")
            
            if st.button("🗑️ Excluir Viagem Inteira", type="primary", use_container_width=True, disabled=not confirmar_exclusao):
                st.session_state.viagens = [v for v in st.session_state.viagens if v['id'] != viagem_atual['id']]
                salvar_viagens(st.session_state.viagens)
                st.rerun()

    # ==========================================
    # ABA 2: ROTEIRO
    # ==========================================
    with abas[1]:
        st.subheader("Roteiro Dia a Dia")
        
        id_rot = st.session_state.edit_id if st.session_state.get('edit_tab') == 'roteiro' else None
        edit_rot = next((x for x in viagem_atual.get('roteiro', []) if x['id'] == id_rot), None) if id_rot else None
        rk = st.session_state.rot_key 
        
        with st.container(border=True):
            st.markdown(f"**{'✏️ Editando Atividade' if id_rot else '➕ Nova Atividade'}**")
            
            c1, c2, c3 = st.columns([2, 1, 1])
            r_nome = c1.text_input("Nome *", value=edit_rot['nome'] if edit_rot else "", key=f"rn_{rk}")
            try: d_val = datetime.datetime.strptime(edit_rot['data'], "%Y-%m-%d").date() if edit_rot else datetime.date.today()
            except: d_val = datetime.date.today()
            r_data = c2.date_input("Data da Atividade", value=d_val, format="DD/MM/YYYY", key=f"rd_{rk}")
            r_hora = c3.time_input("Hora", value=datetime.datetime.strptime(edit_rot['hora'], "%H:%M").time() if edit_rot and edit_rot.get('hora') else None, key=f"rh_{rk}")
            
            c_tipo, c_pago = st.columns(2)
            idx_tipo = 0 if not edit_rot else (0 if edit_rot.get('tipo') == "Por agência" else 1)
            r_tipo = c_tipo.selectbox("Tipo de Passeio", ["Por agência", "Por conta"], index=idx_tipo, key=f"rt_{rk}")
            r_pago = c_pago.checkbox("✅ Passeio já está pago?", value=edit_rot.get('pago', False) if edit_rot else False, key=f"rp_{rk}")
            
            r_info = st.text_area("Anotações (Opcional)", value=edit_rot.get('info', '') if edit_rot else "", key=f"ri_{rk}")
            
            st.markdown("**Custos e Cotação**")
            c_m1, c_m2, c_m3, c_m4 = st.columns(4)
            moedas = ["USD", "EUR", "CLP", "ARS", "BRL"]
            
            moeda_default = edit_rot.get('moeda', 'USD') if edit_rot else 'USD'
            idx_moeda = moedas.index(moeda_default) if moeda_default in moedas else 0
            
            # ATENÇÃO: O on_change é acionado aqui!
            r_moeda = c_m1.selectbox("Moeda", moedas, index=idx_moeda, key=f"rm_{rk}", on_change=on_moeda_change_rot)
            
            # Carrega a cotação (da memória de edição, ou puxada recém pela API)
            cotacao_sugerida = float(edit_rot.get('cotacao', 1.0)) if (edit_rot and r_pago) else buscar_cotacao_api(r_moeda)
            r_cotacao = c_m2.number_input("Cotação R$", min_value=0.0, value=cotacao_sugerida, format="%.5f", disabled=(r_pago and id_rot is not None), key=f"rc_{rk}")
            
            if r_tipo == "Por agência":
                r_passeio = c_m3.number_input("Valor Agência", min_value=0.0, value=float(edit_rot.get('custo_passeio', 0.0)) if edit_rot else 0.0, key=f"rpa_{rk}")
            else:
                r_passeio = 0.0
                c_m3.info("Agência N/A")
                
            r_ingresso = c_m4.number_input("Valor Ingresso", min_value=0.0, value=float(edit_rot.get('custo_ingresso', 0.0)) if edit_rot else 0.0, key=f"rin_{rk}")

            col_b1, col_b2 = st.columns([1, 4])
            if col_b1.button("Salvar Atividade", type="primary", key=f"btn_rot_{rk}"):
                if r_nome:
                    dados = {
                        "id": id_rot or str(uuid.uuid4()), "nome": r_nome, 
                        "data": str(r_data), "hora": r_hora.strftime("%H:%M") if r_hora else "",
                        "tipo": r_tipo, "pago": r_pago, "info": r_info,
                        "moeda": r_moeda, "cotacao": r_cotacao,
                        "custo_passeio": r_passeio, "custo_ingresso": r_ingresso
                    }
                    if id_rot:
                        idx = next(i for i, v in enumerate(viagem_atual['roteiro']) if v['id'] == id_rot)
                        viagem_atual['roteiro'][idx].update(dados)
                    else:
                        viagem_atual.setdefault('roteiro', []).append(dados)
                    
                    salvar_viagens(st.session_state.viagens)
                    st.session_state.edit_id = None
                    st.session_state.edit_tab = None
                    st.session_state.rot_key += 1
                    st.rerun()
            
            if id_rot and col_b2.button("Cancelar Edição", key=f"btn_rot_canc_{rk}"):
                st.session_state.edit_id = None
                st.session_state.rot_key += 1
                st.rerun()

        st.divider()
        rot_ordenado = sorted(viagem_atual.get('roteiro', []), key=lambda x: (x.get('data',''), x.get('hora','')))
        datas = sorted(list(set(r.get('data', '') for r in rot_ordenado)))
        
        for data_atual in datas:
            dt_format = datetime.datetime.strptime(data_atual, "%Y-%m-%d").strftime("%d/%m/%Y") if data_atual else "S/ Data"
            st.markdown(f"### 📅 {dt_format}")
            
            for r in [x for x in rot_ordenado if x.get('data') == data_atual]:
                with st.container(border=True):
                    c_txt, c_btn = st.columns([5, 1])
                    pago_str = "✅ Pago" if r.get('pago') else "⚠️ Pendente"
                    c_txt.markdown(f"**{r.get('hora', '--')} - {r['nome']}** | 🏷️ {r['tipo']} | {pago_str}")
                    if r.get('info'): c_txt.caption(f"ℹ️ {r['info']}")
                    
                    tot_moeda = r.get('custo_passeio', 0) + r.get('custo_ingresso', 0)
                    if tot_moeda > 0:
                        tot_brl = tot_moeda * r.get('cotacao', 1.0)
                        cotacao_texto = str(round(r.get('cotacao', 1.0), 4)).replace('.', ',')
                        c_txt.success(f"💰 {r['moeda']} {formatar_moeda(tot_moeda)} ➔ **R$ {formatar_moeda(tot_brl)}** (Cotação: {cotacao_texto})")
                    
                    if c_btn.button("✏️", key=f"er_{r['id']}"):
                        st.session_state.edit_id = r['id']
                        st.session_state.edit_tab = 'roteiro'
                        st.session_state.rot_key += 1
                        st.rerun()
                    if c_btn.button("🗑️", key=f"dr_{r['id']}"):
                        viagem_atual['roteiro'] = [x for x in viagem_atual['roteiro'] if x['id'] != r['id']]
                        salvar_viagens(st.session_state.viagens)
                        st.rerun()

    # ==========================================
    # ABA 3: FINANCEIRO
    # ==========================================
    with abas[2]:
        st.subheader("Despesas Gerais")
        
        id_fin = st.session_state.edit_id if st.session_state.get('edit_tab') == 'financeiro' else None
        edit_fin = next((x for x in viagem_atual.get('despesas', []) if x['id'] == id_fin), None) if id_fin else None
        fk = st.session_state.fin_key
        
        with st.container(border=True):
            st.markdown(f"**{'✏️ Editando Despesa' if id_fin else '➕ Nova Despesa'}**")
            c1, c2, c3 = st.columns([3, 2, 1])
            f_desc = c1.text_input("Descrição *", value=edit_fin['descricao'] if edit_fin else "", key=f"fd_{fk}")
            cat_list = ['Alimentação', 'Transporte', 'Hospedagem', 'Compras', 'Outros']
            f_cat = c2.selectbox("Categoria", cat_list, index=cat_list.index(edit_fin['categoria']) if edit_fin and edit_fin['categoria'] in cat_list else 0, key=f"fc_{fk}")
            f_pago = c3.checkbox("Pago?", value=edit_fin['pago'] if edit_fin else False, key=f"fp_{fk}")

            c4, c5, c6 = st.columns(3)
            moedas = ["USD", "EUR", "CLP", "ARS", "BRL"]
            moeda_fin_default = edit_fin.get('moeda', 'USD') if edit_fin else 'USD'
            idx_moeda_fin = moedas.index(moeda_fin_default) if moeda_fin_default in moedas else 0
            
            # ATENÇÃO: O on_change é acionado aqui!
            f_moeda = c4.selectbox("Moeda", moedas, index=idx_moeda_fin, key=f"fm_{fk}", on_change=on_moeda_change_fin)
            f_val = c5.number_input("Valor *", min_value=0.0, value=float(edit_fin['valor']) if edit_fin else 0.0, format="%.2f", key=f"fv_{fk}")
            
            cot_fin_sug = float(edit_fin.get('cotacao', 1.0)) if (edit_fin and f_pago) else buscar_cotacao_api(f_moeda)
            f_cot = c6.number_input("Cotação R$", min_value=0.0, value=cot_fin_sug, format="%.5f", disabled=(f_pago and id_fin is not None), key=f"fct_{fk}")
            
            col_bf1, col_bf2 = st.columns([1, 4])
            if col_bf1.button("Salvar Despesa", type="primary", key=f"bf_{fk}"):
                if f_desc and f_val > 0:
                    dados = {"id": id_fin or str(uuid.uuid4()), "descricao": f_desc, "categoria": f_cat, "moeda": f_moeda, "valor": f_val, "cotacao": f_cot, "pago": f_pago}
                    if id_fin:
                        idx = next(i for i, v in enumerate(viagem_atual['despesas']) if v['id'] == id_fin)
                        viagem_atual['despesas'][idx] = dados
                    else:
                        viagem_atual.setdefault('despesas', []).append(dados)
                    salvar_viagens(st.session_state.viagens)
                    st.session_state.edit_id = None
                    st.session_state.edit_tab = None
                    st.session_state.fin_key += 1
                    st.rerun()

            if id_fin and col_bf2.button("Cancelar", key=f"bfc_{fk}"):
                st.session_state.edit_id = None
                st.session_state.fin_key += 1
                st.rerun()

        if viagem_atual.get('despesas'):
            total = sum(d.get('valor', 0) * d.get('cotacao', 1.0) for d in viagem_atual['despesas'])
            st.metric("Custo Total Estimado das Despesas", f"R$ {formatar_moeda(total)}")
            st.divider()
            
            for d in viagem_atual['despesas']:
                c_check, c_desc, c_cat, c_valor, c_del = st.columns([0.5, 3, 2, 3, 1])
                is_pago = c_check.checkbox("Pago", value=d.get('pago', False), key=f"chk_fin_{d['id']}", label_visibility="collapsed")
                if is_pago != d.get('pago', False):
                    d['pago'] = is_pago
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()

                formato_desc = f"~~{d['descricao']}~~" if is_pago else d['descricao']
                c_desc.markdown(formato_desc)
                c_cat.caption(d.get('categoria', 'Outros'))
                val_calc = d.get('valor', 0) * d.get('cotacao', 1.0)
                c_valor.write(f"{d['moeda']} {formatar_moeda(d['valor'])} ➔ **R$ {formatar_moeda(val_calc)}**")
                
                if c_del.button("🗑️", key=f"del_fin_{d['id']}"):
                    viagem_atual['despesas'] = [x for x in viagem_atual['despesas'] if x['id'] != d['id']]
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()

    # ==========================================
    # ABA 4: VOOS
    # ==========================================
    with abas[3]:
        st.subheader("Passagens Aéreas")
        with st.container(border=True):
            st.markdown("**🔎 Busca Inteligente**")
            c_busca1, c_busca2 = st.columns([3, 1])
            codigo_busca = c_busca1.text_input("Código do Voo (Ex: LA750, G3123)")
            if c_busca2.button("Buscar Dados"):
                with st.spinner("Conectando..."):
                    time.sleep(1)
                    resultado = simular_api_voos(codigo_busca)
                    if resultado:
                        st.session_state.voo_temp = resultado
                        st.session_state.voo_temp['codigo'] = codigo_busca.upper()
                        st.success("Dados encontrados!")
                    else:
                        st.error("Voo não encontrado na demonstração.")
            
            st.divider()
            vt = st.session_state.voo_temp
            
            with st.form("form_voo", clear_on_submit=True):
                cv1, cv2 = st.columns(2)
                v_cia = cv1.text_input("Cia Aérea", value=vt.get('cia', ''))
                v_cod = cv2.text_input("Código", value=vt.get('codigo', ''))
                v_ori = cv1.text_input("Origem", value=vt.get('origem', ''))
                v_des = cv2.text_input("Destino", value=vt.get('destino', ''))
                
                cc1, cc2, cc3, cc4 = st.columns(4)
                v_brl = cc1.number_input("Custo Passagem (R$)", min_value=0.0, format="%.2f")
                v_taxas = cc2.number_input("Taxas (R$)", min_value=0.0, format="%.2f")
                v_pts = cc3.number_input("Milhas Utilizadas", min_value=0, step=1000)
                v_status = cc4.selectbox("Status", ["Em cotação", "Comprado"])
                
                if st.form_submit_button("Salvar Voo"):
                    if v_cia and v_ori:
                        viagem_atual.setdefault('voos', []).append({
                            "id": str(uuid.uuid4()), "cia": v_cia, "codigo": v_cod,
                            "origem": v_ori, "destino": v_des, "status": v_status,
                            "custo_brl": v_brl, "taxas_brl": v_taxas, "milhas": v_pts
                        })
                        salvar_viagens(st.session_state.viagens)
                        st.session_state.voo_temp = {}
                        st.rerun()
                    
        for v in viagem_atual.get('voos', []):
            with st.container(border=True):
                c1, c2 = st.columns([5,1])
                badge = "✅ Comprado" if v.get('status') == "Comprado" else "⚠️ Cotação"
                c1.markdown(f"✈️ **{v['cia']} ({v.get('codigo', '--')})** | {badge}")
                c1.markdown(f"{v['origem']} ➔ {v['destino']}")
                c1.caption(f"Custo: R$ {formatar_moeda(v.get('custo_brl',0))} + Taxas: R$ {formatar_moeda(v.get('taxas_brl',0))} | Milhas: {formatar_inteiro(v.get('milhas',0))}")
                if c2.button("🗑️", key=f"dv_{v['id']}"):
                    viagem_atual['voos'] = [x for x in viagem_atual['voos'] if x['id'] != v['id']]
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()

    # ==========================================
    # ABA 5: CARROS
    # ==========================================
    with abas[4]:
        st.subheader("Aluguel de Carro")
        with st.form("form_carro", clear_on_submit=True):
            cc1, cc2 = st.columns(2)
            c_loc = cc1.text_input("Locadora")
            c_ret = cc2.text_input("Local de Retirada")
            cc3, cc4 = st.columns(2)
            c_custo = cc3.number_input("Custo Total (R$)", min_value=0.0)
            c_stat = cc4.selectbox("Status", ["Em cotação", "Alugado"])
            if st.form_submit_button("Salvar Reserva") and c_loc:
                viagem_atual.setdefault('carros', []).append({
                    "id": str(uuid.uuid4()), "locadora": c_loc, "retirada": c_ret,
                    "custo_brl": c_custo, "status": c_stat
                })
                salvar_viagens(st.session_state.viagens)
                st.rerun()
                
        for c in viagem_atual.get('carros', []):
            with st.container(border=True):
                col1, col2 = st.columns([5,1])
                b_car = "✅ Alugado" if c.get('status') == "Alugado" else "⚠️ Cotação"
                col1.markdown(f"🚗 **{c['locadora']}** | {b_car}")
                col1.markdown(f"Retirada: {c.get('retirada', '--')} | Custo: R$ {formatar_moeda(c.get('custo_brl', 0))}")
                if col2.button("🗑️", key=f"dc_{c['id']}"):
                    viagem_atual['carros'] = [x for x in viagem_atual['carros'] if x['id'] != c['id']]
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()

    # ==========================================
    # ABA 6: CHECKLIST
    # ==========================================
    with abas[5]:
        st.subheader("Coisas a Fazer / Comprar")
        with st.form("f_check", clear_on_submit=True):
            nova_tarefa = st.text_input("Nova tarefa:")
            if st.form_submit_button("Adicionar") and nova_tarefa:
                viagem_atual.setdefault('tarefas', []).append({"id": str(uuid.uuid4()), "texto": nova_tarefa, "concluido": False})
                salvar_viagens(st.session_state.viagens)
                st.rerun()
            
        for t in viagem_atual.get('tarefas', []):
            if st.checkbox(t['texto'], value=t['concluido'], key=t['id']):
                if not t['concluido']:
                    t['concluido'] = True
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()
            else:
                if t['concluido']:
                    t['concluido'] = False
                    salvar_viagens(st.session_state.viagens)
                    st.rerun()
                    