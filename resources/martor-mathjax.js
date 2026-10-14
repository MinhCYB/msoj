jQuery(function ($) {
    var mathLoad;
    $(document).on('martor:preview', function (e, $content) {
        function update_math() {
            MathJax.startup.promise.then(function () {
                return MathJax.typesetPromise([$content[0]]);
            }).then(function () {
                $content.find('.tex-image').hide();
                $content.find('.tex-text').show();
            });
        }

        var $jax = $content.find('.require-mathjax-support');
        if ($jax.length) {
            if (window.MathJax && MathJax.startup && MathJax.startup.promise) {
                update_math();
            } else {
                if (!mathLoad) {
                    mathLoad = $.ajax({
                        url: $jax.attr('data-config'), dataType: 'script', cache: true
                    }).then(function () {
                        if ($jax.attr('data-dollar-delimiters') === 'true') {
                            MathJax.tex.inlineMath.push(['$', '$']);
                        }
                        window.MathJax.startup = {typeset: false};
                        return $.ajax({
                            url: '/static/vnoj/mathjax/3.2.0/es5/tex-chtml.min.js',
                            dataType: 'script', cache: true
                        });
                    });
                    mathLoad.fail(function () {
                        mathLoad = null;
                        console.error('Unable to load editor mathematics.');
                    });
                }
                mathLoad.then(update_math);
            }
        }
    })
});
