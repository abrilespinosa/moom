// Leaflet de mentira, solo para los tests.
//
// El de verdad viene de unpkg por CDN. Cargarlo en cada test ataría la suite
// a que un servidor ajeno esté en pie, que es justo lo que el resto de tests
// evita a conciencia. Y no hace falta: aquí no se prueba Leaflet —eso es
// código de otros y ya está probado— sino el buscador, los paneles y el
// cambio de vistas, que solo necesitan que el mapa no reviente al crearse.
//
// Implementa EXACTAMENTE lo que app.js usa, que es poco (comprobado con grep
// sobre el archivo). Si algún día app.js llama a algo que no esté aquí, el
// test fallará con "no es una función", que es un error legible y avisa de
// que hay que ampliar este archivo.
window.L = (function () {
  function capa() {
    const self = {
      _enMapa: false,
      addTo(mapa) {
        this._enMapa = true;
        mapa._capas.add(this);
        return this;
      },
      remove() {
        this._enMapa = false;
        return this;
      },
      on() {
        return this;
      },
      setIcon(icono) {
        this._icono = icono;
        return this;
      },
      setOpacity(valor) {
        this._opacidad = valor;
        return this;
      },
      bindTooltip() {
        return this;
      },
      bindPopup() {
        return this;
      },
      setLatLng(pos) {
        this._pos = pos;
        return this;
      },
      getLatLng() {
        // app.js se lo pasa a bounds.contains(), que abajo acepta cualquier
        // cosa: el filtro por área visible no se prueba desde aquí.
        return this._pos;
      },
    };
    return self;
  }

  return {
    map() {
      const mapa = {
        _capas: new Set(),
        // Zoom por encima de ZOOM_MINIMO_PARADAS (15) para que las paradas
        // se dibujen: si devolviera el zoom inicial de 14, el mapa estaría
        // vacío y varios tests no tendrían nada que mirar.
        _zoom: 16,
        setView() {
          return mapa;
        },
        getZoom() {
          return mapa._zoom;
        },
        // Todo entra en pantalla: el recorte por área visible es cosa de
        // Leaflet y no se prueba aquí.
        getBounds() {
          return { contains: () => true };
        },
        hasLayer(capa) {
          return mapa._capas.has(capa);
        },
        removeLayer(capa) {
          mapa._capas.delete(capa);
          return mapa;
        },
        invalidateSize() {
          return mapa;
        },
        on() {
          return mapa;
        },
      };
      return mapa;
    },
    tileLayer() {
      return capa();
    },
    marker(pos) {
      const m = capa();
      m._pos = pos;
      return m;
    },
    icon(opciones) {
      return opciones;
    },
    divIcon(opciones) {
      return opciones;
    },
  };
})();
