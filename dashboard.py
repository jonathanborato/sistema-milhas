# --- CARTEIRA ---
    elif menu == "Minha Carteira":
        st.header("💼 Carteira Inteligente")
        
        # --- ÁREA DE ADIÇÃO MELHORADA ---
        with st.expander("➕ Adicionar Novo Lote", expanded=True):
            with st.form("add_carteira"):
                c1, c2, c3 = st.columns(3)
                
                # Seleção do Programa
                p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo", "Esfera"])
                
                # Quantidade de Milhas
                q = c2.number_input("Quantidade de Milhas", min_value=1000, step=1000, value=1000)
                
                # MUDANÇA AQUI: Pedimos o CPM (Custo por Milheiro) em vez do Total
                cpm_input = c3.number_input("Quanto pagou no milheiro? (CPM)", min_value=0.0, value=35.00, step=0.50, help="Ex: Se comprou Livelo a R$35,00, coloque 35.00")
                
                # O sistema calcula o total sozinho
                custo_total_calculado = (q / 1000) * cpm_input
                st.caption(f"💰 Custo Total do Lote: {formatar_real(custo_total_calculado)}")

                if st.form_submit_button("💾 Salvar Lote na Carteira"):
                    # Salva passando o total calculado
                    ok, msg = adicionar_carteira(user['email'], p, q, custo_total_calculado)
                    if ok: 
                        st.success("Lote adicionado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else: 
                        st.error(f"Erro ao salvar: {msg}")
        
        st.divider()

        # --- VISUALIZAÇÃO E CÁLCULOS ---
        dfc = ler_carteira_usuario(user['email'])
        
        if not dfc.empty:
            patrimonio = 0
            custo_total = 0
            view_data = []
            
            for _, row in dfc.iterrows():
                prog_nome = row['programa'].split()[0]
                
                # 1. Busca Cotação Hotmilhas (Robô)
                val_hot = 0.0
                if not df_cotacoes.empty:
                    f = df_cotacoes[df_cotacoes['programa'].str.contains(prog_nome, case=False, na=False)]
                    if not f.empty: val_hot = f.iloc[-1]['cpm']
                
                # 2. Busca Cotação P2P (Nuvem)
                val_p2p = pegar_ultimo_p2p(prog_nome)
                
                # 3. Define Melhor Preço (Valuation)
                melhor_preco = max(val_hot, val_p2p)
                
                if melhor_preco == 0:
                    origem = "Sem Cotação"
                    # Se não tem cotação, assumimos preço de custo para não quebrar o gráfico
                    # ou deixamos zerado. Vamos deixar zerado para alertar.
                else:
                    origem = "Hotmilhas" if val_hot >= val_p2p else "P2P"
                
                # Conversão segura para float
                qtd = float(row['quantidade'])
                custo = float(row['custo_total'])
                cpm_pago = float(row['cpm_medio'])
                
                # Cálculo Financeiro
                val_venda = (qtd / 1000) * melhor_preco
                lucro = val_venda - custo
                
                # Acumuladores
                patrimonio += val_venda
                custo_total += custo
                
                view_data.append({
                    "ID": row['id'], 
                    "Programa": row['programa'], 
                    "Qtd": f"{qtd:,.0f}".replace(',', '.'), 
                    "CPM Pago": formatar_real(cpm_pago), 
                    "Custo Total": formatar_real(custo),
                    "Melhor Cotação": f"{formatar_real(melhor_preco)} ({origem})", 
                    "Valor Venda": formatar_real(val_venda),
                    "Lucro (Hoje)": formatar_real(lucro),
                    "val_lucro_raw": lucro # Usado para colorir, depois removido
                })
            
            # KPIs do Topo
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Investido (Custo)", formatar_real(custo_total))
            k2.metric("Patrimônio Atual (Venda)", formatar_real(patrimonio))
            
            delta_val = patrimonio - custo_total
            delta_perc = ((patrimonio/custo_total)-1)*100 if custo_total > 0 else 0
            k3.metric("Lucro/Prejuízo Projetado", formatar_real(delta_val), delta=f"{delta_perc:.1f}%")
            
            st.divider()
            
            # Tabela Detalhada
            df_view = pd.DataFrame(view_data)
            
            def color_lucro(val):
                if isinstance(val, str) and "-" in val: 
                    return 'color: #d9534f; font-weight: bold;' # Vermelho
                return 'color: #28a745; font-weight: bold;' # Verde

            st.dataframe(
                df_view.drop(columns=['val_lucro_raw']).style.applymap(color_lucro, subset=['Lucro (Hoje)']), 
                use_container_width=True
            )
            
            # Botão de Remover
            c_del1, c_del2 = st.columns([3, 1])
            with c_del2:
                rid = st.number_input("ID para excluir", step=1)
                if st.button("🗑️ Excluir Lote"):
                    remover_carteira(rid)
                    st.success("Lote removido!")
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.info("📭 Sua carteira está vazia. Adicione seu primeiro lote acima.")
