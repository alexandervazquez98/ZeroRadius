import { Component } from 'react';

class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, info) {
        console.error('[ErrorBoundary]', error, info.componentStack);
    }

    handleReload() {
        window.location.reload();
    }

    handleHome() {
        window.location.href = '/';
    }

    render() {
        if (!this.state.hasError) return this.props.children;

        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
                <div className="w-20 h-20 rounded-full bg-amber-100 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                </div>

                <div>
                    <h2 className="text-2xl font-black text-slate-800">Algo salió mal</h2>
                    <p className="text-slate-500 mt-2 max-w-sm">Ocurrió un error inesperado. Podés volver al inicio o recargar la página.</p>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={this.handleHome}
                        className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 font-semibold hover:bg-slate-200 transition-colors"
                    >
                        Volver al inicio
                    </button>
                    <button
                        onClick={this.handleReload}
                        className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 transition-colors"
                    >
                        Recargar página
                    </button>
                </div>

                {import.meta.env.DEV && this.state.error && (
                    <details className="mt-4 w-full max-w-2xl text-left">
                        <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-600">Detalles del error (dev only)</summary>
                        <pre className="mt-2 p-4 rounded-lg bg-slate-900 text-rose-400 text-xs overflow-auto whitespace-pre-wrap">
                            {this.state.error.toString()}
                            {'\n\n'}
                            {this.state.error.stack}
                        </pre>
                    </details>
                )}
            </div>
        );
    }
}

export default ErrorBoundary;
