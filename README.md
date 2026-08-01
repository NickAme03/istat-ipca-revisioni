# IPCA Italia, storia delle revisioni

Questo repository conserva con Git una sola serie ISTAT: indice armonizzato dei prezzi al consumo, indice generale per l'Italia, dati mensili, base 2025 uguale a 100.

La fonte è il [Web Service SDMX di ISTAT](https://www.istat.it/classificazioni-e-strumenti/web-services-sdmx/). La query usa il dataflow `168_761` e la chiave `M.IT.87.4.00`:

`https://esploradati.istat.it/SDMXWS/rest/data/168_761/M.IT.87.4.00`

La serie cambia mensilmente. Il workflow controlla la fonte ogni lunedì alle 08:17 UTC. Crea un commit soltanto quando il contenuto normalizzato di `data/ipca.csv` cambia. In questo modo la cronologia mostra nuovi dati e revisioni, non semplici esecuzioni dello scraper.

## Contenuto

`data/ipca.csv` contiene:

- `period`, mese nel formato `AAAA-MM`;
- `index_2025_100`, valore dell'indice;
- `status`, stato ISTAT dell'osservazione, per esempio `p` quando il dato è provvisorio.

Lo script usa soltanto la libreria standard di Python. Ogni esecuzione fa una sola query. Gli eventuali tentativi successivi sono distanziati di almeno 12,5 secondi dal codice, così il processo non supera il limite ISTAT di cinque query al minuto.

Esecuzione locale:

```shell
python scrape.py
```

## Cosa non copre

- Non include sottocategorie di consumo, dati regionali, NIC, FOI, pesi o medie annue.
- Non ricostruisce revisioni avvenute prima del primo commit del repository.
- Non trasforma un dato provvisorio in definitivo. Conserva lo stato pubblicato da ISTAT.
- Non garantisce il giorno di pubblicazione. La fonte è mensile, il controllo è settimanale.
- Non gestisce automaticamente un futuro cambio di base o di dataflow ISTAT.
- Non può impedire a GitHub di disabilitare il workflow pianificato dopo 60 giorni senza attività del repository. Se la fonte smette di cambiare, il proprietario deve controllare lo stato delle Actions.

## Attribuzione e licenze

Fonte: Istituto Nazionale di Statistica, ISTAT. I dati sono pubblicati con [licenza Creative Commons Attribuzione 4.0](https://creativecommons.org/licenses/by/4.0/), e in questo repository restano sotto quella licenza.

Il codice, cioè `scrape.py` e il workflow, è distribuito con [licenza MIT](LICENSE).
