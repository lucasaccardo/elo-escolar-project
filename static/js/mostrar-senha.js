/* Botao de mostrar/ocultar senha.
 *
 * O botao e criado AQUI, em JavaScript, e nao escrito no HTML. A razao e
 * que ele so faz sentido se houver JavaScript: um olhinho que nao abre
 * nada seria pior do que olhinho nenhum. Sem script, o campo continua
 * funcionando exatamente como antes - e as telas essenciais do sistema
 * seguem utilizaveis, que e um compromisso do projeto.
 */
(function () {
    'use strict';

    var OLHO =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
        ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"' +
        ' aria-hidden="true">' +
        '<path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z"/>' +
        '<circle cx="12" cy="12" r="3.2"/></svg>';

    var OLHO_CORTADO =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
        ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"' +
        ' aria-hidden="true">' +
        '<path d="M9.9 5.7A9.9 9.9 0 0 1 12 5.5c7 0 10.5 6.5 10.5 6.5a18 18 0 0 1-3.1 3.9"/>' +
        '<path d="M6.3 7.8A17.6 17.6 0 0 0 1.5 12S5 18.5 12 18.5a9.8 9.8 0 0 0 4.1-.86"/>' +
        '<path d="M10.2 10.3a3.2 3.2 0 0 0 4.4 4.4"/>' +
        '<path d="M3 3l18 18"/></svg>';

    function preparar(campo) {
        var caixa = document.createElement('div');
        caixa.className = 'campo-senha';
        campo.parentNode.insertBefore(caixa, campo);
        caixa.appendChild(campo);

        var botao = document.createElement('button');
        // Sem type="button" o clique envia o formulario: dentro de um
        // <form>, o padrao de um <button> e submit.
        botao.type = 'button';
        botao.className = 'campo-senha__olho';
        botao.innerHTML = OLHO;
        botao.setAttribute('aria-pressed', 'false');
        botao.setAttribute('aria-label', 'Mostrar a senha');
        botao.title = 'Mostrar a senha';
        caixa.appendChild(botao);

        botao.addEventListener('click', function () {
            var estaVisivel = campo.type === 'text';
            campo.type = estaVisivel ? 'password' : 'text';

            var rotulo = estaVisivel ? 'Mostrar a senha' : 'Ocultar a senha';
            botao.innerHTML = estaVisivel ? OLHO : OLHO_CORTADO;
            botao.setAttribute('aria-pressed', String(!estaVisivel));
            botao.setAttribute('aria-label', rotulo);
            botao.title = rotulo;

            // Devolve o cursor ao campo, no fim do texto, para quem estava
            // digitando nao perder o lugar.
            campo.focus();
            var fim = campo.value.length;
            try { campo.setSelectionRange(fim, fim); } catch (e) { /* ok */ }
        });
    }

    function iniciar() {
        var campos = document.querySelectorAll('input[type="password"]');
        Array.prototype.forEach.call(campos, preparar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
