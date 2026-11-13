# Revisão bibliográfica aplicada — Score-Driven Models na previsão diária de carga do ONS

**Projeto:** PUC-Rio / DEE, Score-Driven Models (2026)  
**Autores do projeto:** Carlos Souza e Gabriel Matz  
**Escopo da revisão:** evidências bibliográficas verificadas e recomendações de implementação, não resultados de modelos GAS já estimados.

## 1. Pergunta e contribuição

**Pergunta:** a modelagem Score-Driven da média e da incerteza, combinada à sazonalidade semanal/anual e efeitos de calendário, fornece previsões probabilísticas mais bem calibradas para a carga diária do SIN do que referências sazonais?

**Contribuição aplicada proposta:** comparar GAS normal, GAS t-Student, GAS com escala dinâmica, efeitos sazonais dinâmicos e cenários futuros obtidos por simulação sequencial; tratar explicitamente duas mudanças na definição operacional do ONS (03/2021 e 29/04/2023). Uma extensão opcional concilia as previsões regionais para que somem ao SIN.

## 2. Cuidado essencial com os dados

ONS: https://dados.ons.org.br/dataset/carga-energia

- Série diária, medida em MWmed, quatro subsistemas SE, S, NE, N; SIN é a soma dos quatro.
- Até fevereiro/2021, a série diária representava a carga atendida por unidades despachadas/programadas pelo ONS.
- Entre março/2021 e abril/2023, incluiu previsão de geração de unidades não despachadas.
- A partir de 29/04/2023, incorporou estimativa de micro e minigeração distribuída (MMGD).
- A base pública é revisável. Registre data de extração, hashes e versão do conjunto.
- Não confundir efeito de quebra de mensuração com mudança econômica na demanda.

O script `baixar_carga_ons.py` da versão consultada do repositório usa API CKAN e Parquet desde 2000. O script `sarima_carga.py` aplica SARIMA(1,1,1)x(1,1,1)[7] em log e reserva os últimos 365 dias. Isso não implementa a avaliação 2016–2022 / 2023–2024 / 2025–2026 proposta no README.

A saída SARIMA armazenada em `resultados/sarima_metricas.csv`, para SIN, é MAPE 4,6842%, MAE 3764,86 MWmed, RMSE 4550,76 MWmed, Ljung-Box em lag 14 p=1,48e-11. Não são métricas do modelo GAS e não são comparáveis ainda a futuros experimentos com outro intervalo. Em `sarima_carga.py`, a exponenciação da média prevista em log fornece uma mediana na escala original sob lognormalidade; para média original, requer correção de retransfomação. A interpolação antes da divisão treino/teste pode usar valores posteriores à origem em certos pontos; rever para eliminar vazamento.

## 3. Revisão comparativa dos trabalhos

| Fonte | Contribuição documentada | Como usar no projeto | Prioridade |
|---|---|---|---|
| Creal, Koopman & Lucas (2013) | Classe GAS, escore escalado, máxima verossimilhança | Derivação geral da recursão e escolha de escala | Crítica |
| Harvey (2022) | Síntese de filtros score-driven, inferência e aplicações | Justificação conceitual e interpretação | Crítica |
| Artemova, Blasques, van Brummelen & Koopman (2022) | Metodologia e teoria de modelos SDM | Formulação, parametrização e estimação | Alta |
| Harvey & Luati (2014) | Filtragem robusta t-Student com tendência e sazonalidade | Substituir inovações gaussianas em presença de outliers | Crítica |
| Ardia, Boudt & Catania (2019) | Pacote R `GAS` para estimação e previsão | Benchmark cruzado/verificação da implementação | Alta |
| De Livera, Hyndman & Snyder (2011) | TBATS, Fourier dinâmico e períodos sazonais complexos | Modelar ciclos 7/365,25; benchmark TBATS | Crítica |
| Taylor (2010) | Extensão de previsões de demanda elétrica para três sazonalidades | Fundamentar múltiplas sazonalidades e variáveis de calendário | Alta |
| Soares & Medeiros (2008) | Decomposição carga elétrica no Brasil: tendência, Fourier, dias especiais + dinâmica | Referência contextual brasileira mais diretamente aplicável | Crítica |
| Fan & Hyndman (2012) | Modelo aditivo semiparamétrico com calendário, carga defasada e temperaturas | Construir GAM como benchmark forte | Alta |
| Goude, Nedellec & Kong (2014) | Previsão de carga local por modelos aditivos | Regressões não lineares e efeitos climáticos | Média |
| Gaillard, Goude & Nedellec (2016) | Previsões probabilísticas de energia com quantGAM e cenários meteorológicos | Modelagem probabilística e comparação por quantis | Alta |
| Hong & Fan (2016) | Revisão de previsão probabilística de carga | Justificativa de intervalos/quantis e avaliação | Crítica |
| Zimmermann & Ziel (2025) | GAM interpretável com temperatura, feriados, estados ETS e correção AR | Inspiração de covariáveis/benchmarks e ablação | Alta |
| Hyndman & Koehler (2006) | MASE e crítica a medidas de acurácia | Protocolo MAE/RMSE/MASE por horizonte | Alta |
| Gneiting & Raftery (2007) | Regras de pontuação próprias, CRPS e intervalo | Avaliação de densidades e quantis preditivos | Crítica |
| Diebold & Mariano (1995) | Teste de igualdade de precisão preditiva | Comparação com cautela para erros serialmente dependentes | Média |
| Dunn & Smyth (1996) | Resíduos quantílicos normalizados | PIT e diagnósticos na escala z | Alta |
| Wickramasuriya, Athanasopoulos & Hyndman (2019) | Reconciliação hierárquica MinT | SIN = SE + S + NE + N em cenário de extensão | Opcional |

## 4. Modelos candidatos e equações

### M0: benchmarks

- Naive: \(\widehat Y_{t+h|t}=Y_t\).
- Sazonal naive semanal: \(\widehat Y_{t+h|t}=Y_{t+h-7\lceil h/7\rceil}\), referência observável no tempo \(t\); equivalente à última observação do mesmo dia da semana.
- SARIMA sazonal semanal com Fourier anual e dummies de feriados (SARIMAX ou regressão harmônica dinâmica).
- TBATS com períodos (7, 365,25).
- GAM baseado em calendário e efeitos climáticos, se as covariáveis forem conhecidas na origem.

### M1: GAS normal sazonal, escore de localização

\[
Y_t\mid\mathcal F_{t-1}\sim N(m_t,\sigma^2),\qquad
m_t=\mu_t+W_{d(t)}+\sum_{j=1}^{K}[a_j\cos(2\pi jt/365.25)+b_j\sin(2\pi jt/365.25)]+x_t^\top\beta.
\]

Com \(\sum_{d=1}^{7}W_d=0\), \(e_t=Y_t-m_t\):

\[
\nabla_t^\mu=e_t/\sigma^2,\quad \mathcal I_t^\mu=1/\sigma^2,\quad s_t=\mathcal I_t^{-1}\nabla_t=e_t,
\qquad\mu_{t+1}=\omega+B\mu_t+A s_t.
\]

Cuidado com identificação: não duplicar intercepto fixo com nível GAS sem uma convenção. Se houver tendência persistente, discutir B próximo de 1, diferença do nível, ou componente explícita de inclinação.

### M2: GAS t-Student sazonal (robusto)

\[
Y_t\mid\mathcal F_{t-1}\sim t_\nu(m_t,\sigma),\qquad
\frac{\partial\ell_t}{\partial m_t}=\frac{(\nu+1)(Y_t-m_t)}{\nu\sigma^2+(Y_t-m_t)^2}.
\]

O escore reage de forma menos explosiva a grandes resíduos. A escala \(\sigma\) está definida como *parâmetro de escala* da t, não seu desvio-padrão. Estimar \(\nu>2\) quando desejar variância finita. Comparar AIC/BIC, PIT, CRPS e resultados OOS.

### M3: GAS normal com escala variante

\[
Y_t\mid\mathcal F_{t-1}\sim N(m_t,e^{h_t}),\qquad r_t=Y_t-m_t,
\]
\[
\nabla^{h}_t=\tfrac12\left(r_t^2e^{-h_t}-1\right),\qquad \mathcal I_t^{h}=\tfrac12,\qquad
s_t^h=r_t^2e^{-h_t}-1,
\]
\[
h_{t+1}=\omega_h+B_h h_t+A_h s_t^h.
\]

Permite erro preditivo mais disperso em dias de choque. É a extensão mais direta se resíduos ao quadrado apresentarem autocorrelação.

### M4: sazonalidade dinâmica (extensão)

\[
m_t=\mu_t+c_t^\top\gamma_t,\qquad
c_t=(\cos(2\pi t/P),\sin(2\pi t/P),\ldots)^\top,
\quad\gamma_{t+1}=D\gamma_t+G\,c_t\,\frac{Y_t-m_t}{\sigma^2}.
\]

Essa é uma proposta de implementação inspirada na literatura, não uma fórmula copiada de um artigo. Para observação univariada com múltiplos coeficientes, a matriz \(c_t c_t^\top/\sigma^2\) tem posto 1; não tentar inverter a matriz de informação de Fisher completa sem regularização/estrutura apropriada. Compare a versão fixa e a dinâmica para avaliar se a amplitude sazonal muda.

### M5: GAS Gama com ligação log (teste de sensibilidade)

Se a carga em MWmed for estritamente positiva, podemos investigar:

\[
Y_t\mid\mathcal F_{t-1}\sim\operatorname{Gamma}(\alpha,\lambda_t/\alpha)\quad\text{(forma, escala)},\quad \eta_t=\log\lambda_t,
\]
\[
E(Y_t\mid\mathcal F_{t-1})=\lambda_t,\quad
\operatorname{Var}(Y_t\mid\mathcal F_{t-1})=\lambda_t^2/\alpha,
\quad\nabla_t^{\eta}=\alpha\left(Y_t/\lambda_t-1\right),\quad
\mathcal I_t^{\eta}=\alpha,
\quad s_t=Y_t/\lambda_t-1.
\]

O teste deve ser diagnóstico, pois a relação \(\operatorname{Var}(Y_t)\propto E(Y_t)^2\) é uma hipótese forte, e a distribuição não é preferível à t ou à lognormal por ser positiva.

## 5. Previsões multi-passos e Monte Carlo

No instante de origem \(t\), após estimar parâmetros fixos e filtrar o estado \(f_{t+1|t}\), para cada trajetória \(j=1,\ldots,M\):

1. Simular \(Y_{t+1}^{(j)}\) da densidade condicional, com sazonalidade e calendário apropriados.
2. Calcular score com a **observação simulada** dessa trajetória.
3. Atualizar estado para \(t+2\) nessa trajetória.
4. Continuar até \(h=H\) e guardar a matriz \(M\times H\).

Resumo no horizonte \(h\):

\[
\widehat E(Y_{t+h}|\mathcal F_t)=M^{-1}\sum_jY_{t+h}^{(j)},\qquad
\widehat Q_p(Y_{t+h}|\mathcal F_t)=\operatorname{quantile}_p\{Y_{t+h}^{(j)}\}_{j=1}^M.
\]

Usar várias sementes e Monte Carlo suficientemente grande para estabilizar quantis; sugestão prática: 2.000–10.000 trajetórias por origem, com teste de estabilidade. Não confundir esse procedimento com filtro de partículas reponderado/reamostrado. A previsão de \(k>1\) requer integração sobre trajetórias futuras não observadas; não substituir o score futuro pela observação efetiva do teste.

## 6. Avaliação experimental

- Treino inicial 2016-01-01 a 2022-12-31.
- Teste 1: 2023-01-01 a 2024-12-31, parâmetros fixos; atualizar estado com informação disponível a cada origem.
- Reestimar com histórico disponível até 2024-12-31.
- Teste 2: 2025-01-01 ao final disponível de 2026.
- Horizontes candidatos h=1, 7 e 14 dias. Cada origem usa só a informação disponível naquela data.
- Fazer seleção de K e hiperparâmetros dentro do treino mediante validação temporal, nunca usando os testes finais.
- Reportar MAE/RMSE/MASE; para previsões probabilísticas, CRPS, pinball loss, cobertura e largura de intervalos de 50/80/90/95%.
- Para um modelo de densidade contínua, PIT = F_t(Y_t); quantile residual = Phi^{-1}(PIT). Testar uniformidade e independência, inclusive autocorrelação do PIT transformado.
- Usar comparação por horizonte, com diferenças de perdas por origem; teste Diebold-Mariano com cuidado para sobreposição dos erros e mudanças estruturais.
- Abrir tabelas específicas para antes/depois de 2023 e para dias úteis, fins de semana, feriados e extremos.

## 7. Um risco de vazamento que precisa ser evitado

Previsão para 2023-01-07 não pode usar temperatura observada em 2023-01-07, a menos que ela já fosse conhecida na origem. Dados ERA5 são reanálise histórica, ótimos para explicar o passado e treinar modelos, mas **não** substituem previsões meteorológicas emitidas em tempo real. Se não houver arquivo de previsões meteorológicas históricas, escolher covariáveis futuras determinísticas (feriados, dias da semana, Fourier) ou apresentar resultados com temperatura realizada como análise *oráculo*, claramente fora da avaliação operacional.

Fontes complementares: INMET BDMEP https://portal.inmet.gov.br/servicos/bdmep-dados-hist%C3%B3ricos e ECMWF ERA5 https://www.ecmwf.int/en/forecasts/datasets/complete-era5-global-atmospheric-reanalysis.

## 8. Plano de implementação priorizado

1. Corrigir benchmark SARIMA: iniciar em 2016, evitar interpolação com informação futura, corrigir média de retransfomação, 2 testes e horizontes fixos.
2. Gerar EDA detalhada com datas de quebra, sazonalidade 7/365,25, periodograma, feriados.
3. M1 GAS normal: função de log-verossimilhança, filtro, otimização e diagnóstico.
4. M2 GAS t-Student: robustez, normalização PIT, comparação de precisão.
5. M3 GAS com variância dinâmica: comparar apenas se heterocedasticidade residual for relevante.
6. Baselines fortes: Fourier + ARMA, TBATS e GAM.
7. M4 dinâmica sazonal e M5 Gamma como extensões (só se melhorarem a avaliação).
8. Extensão regional: modelos para SE, S, NE, N e reconciliação para SIN.

Ablation plan: sem feriado; sem Fourier anual; sem termo de temperatura; nível GAS fixo; variância dinâmica desligada; Student-t versus Normal; efeitos de quebra com e sem dummies. Todas as ablações devem usar os mesmos blocos de treino/teste.

## 9. Bibliografia verificada

1. Creal, D., Koopman, S. J. & Lucas, A. (2013). *Generalized autoregressive score models with applications*. Journal of Applied Econometrics 28, 777–795. https://doi.org/10.1002/jae.1279
2. Harvey, A. C. (2022). *Score-Driven Time Series Models*. Annual Review of Statistics and Its Application 9, 321–342. https://doi.org/10.1146/annurev-statistics-040120-021023
3. Artemova, M., Blasques, F., van Brummelen, J. & Koopman, S. J. (2022). *Score-Driven Models: Methodology and Theory*. Oxford Research Encyclopedia of Economics and Finance. https://doi.org/10.1093/acrefore/9780190625979.013.672
4. Harvey, A. C. & Luati, A. (2014). *Filtering with heavy tails*. JASA 109, 1112–1122. https://doi.org/10.1080/01621459.2014.887011
5. Ardia, D., Boudt, K. & Catania, L. (2019). *Generalized Autoregressive Score Models in R: The GAS Package*. Journal of Statistical Software 88(6). https://doi.org/10.18637/jss.v088.i06
6. De Livera, A. M., Hyndman, R. J. & Snyder, R. D. (2011). *Forecasting time series with complex seasonal patterns using exponential smoothing*. JASA 106, 1513–1527. https://doi.org/10.1198/jasa.2011.tm09771
7. Taylor, J. W. (2010). *Triple seasonal methods for short-term electricity demand forecasting*. European Journal of Operational Research 204, 139–152. https://doi.org/10.1016/j.ejor.2009.10.003
8. Soares, L. J. & Medeiros, M. C. (2008). *Modeling and forecasting short-term electricity load: A comparison of methods with an application to Brazilian data*. International Journal of Forecasting 24, 630–644. https://doi.org/10.1016/j.ijforecast.2008.08.003
9. Fan, S. & Hyndman, R. J. (2012). *Short-term load forecasting based on a semi-parametric additive model*. IEEE Transactions on Power Systems 27, 134–141. https://doi.org/10.1109/TPWRS.2011.2162082
10. Goude, Y., Nedellec, R. & Kong, N. (2014). *Local short and middle term electricity load forecasting with semi-parametric additive models*. IEEE Transactions on Smart Grid 5, 440–446. https://doi.org/10.1109/TSG.2013.2278425
11. Gaillard, P., Goude, Y. & Nedellec, R. (2016). *Additive models and robust aggregation for GEFCom2014 probabilistic electric load and electricity price forecasting*. International Journal of Forecasting. https://doi.org/10.1016/j.ijforecast.2015.12.001
12. Hong, T. & Fan, S. (2016). *Probabilistic electric load forecasting: A tutorial review*. International Journal of Forecasting 32, 914–938. https://doi.org/10.1016/j.ijforecast.2015.11.011
13. Zimmermann, M. & Ziel, F. (2025). *Efficient mid-term forecasting of hourly electricity load using generalized additive models*. Applied Energy 388, 125444. https://doi.org/10.1016/j.apenergy.2025.125444
14. Hyndman, R. J. & Koehler, A. B. (2006). *Another look at measures of forecast accuracy*. International Journal of Forecasting 22, 679–688. https://doi.org/10.1016/j.ijforecast.2006.03.001
15. Gneiting, T. & Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation*. JASA 102, 359–378. https://doi.org/10.1198/016214506000001437
16. Diebold, F. X. & Mariano, R. S. (1995). *Comparing predictive accuracy*. Journal of Business & Economic Statistics 13, 253–263. https://doi.org/10.1080/07350015.1995.10524599
17. Dunn, P. K. & Smyth, G. K. (1996). *Randomized quantile residuals*. Journal of Computational and Graphical Statistics 5, 236–244. https://doi.org/10.1080/10618600.1996.10474708
18. Wickramasuriya, S. L., Athanasopoulos, G. & Hyndman, R. J. (2019). *Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization*. JASA 114, 804–819. https://doi.org/10.1080/01621459.2018.1448825
19. Hyndman, R. J., Ahmed, R. A., Athanasopoulos, G. & Shang, H. L. (2011). *Optimal combination forecasts for hierarchical time series*. Computational Statistics & Data Analysis 55, 2579–2589. https://doi.org/10.1016/j.csda.2011.03.006
20. Taylor, J. W. & McSharry, P. E. (2007). *Short-Term Load Forecasting Methods: An Evaluation Based on European Data*. IEEE Transactions on Power Systems. https://doi.org/10.1109/TPWRS.2007.907583
21. Diebold, F. X., Gunther, T. A. & Tay, A. S. (1998). *Evaluating Density Forecasts, with Applications to Financial Risk Management*. International Economic Review 39, 863–883. https://www.nber.org/papers/t0215

**Leitura prioritária:** Creal (2013), Soares & Medeiros (2008), De Livera et al. (2011), Harvey & Luati (2014), Hong & Fan (2016), Gneiting & Raftery (2007), Zimmermann & Ziel (2025).