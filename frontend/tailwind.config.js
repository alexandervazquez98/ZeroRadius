/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            animation: {
                fadeIn: 'fadeIn 0.2s ease-out',
                slideInRight: 'slideInRight 0.25s ease-out',
                slideUp: 'slideUp 0.3s ease-out',
                'toast-in': 'toastIn 0.25s ease-out',
                'toast-progress': 'toastProgress linear forwards',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideInRight: {
                    '0%': { transform: 'translateX(100%)' },
                    '100%': { transform: 'translateX(0)' },
                },
                slideUp: {
                    '0%': { transform: 'translateY(100%)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                toastIn: {
                    '0%': { transform: 'translateX(110%)', opacity: '0' },
                    '100%': { transform: 'translateX(0)', opacity: '1' },
                },
                toastProgress: {
                    '0%': { width: '100%' },
                    '100%': { width: '0%' },
                },
            },
        },
    },
    plugins: [],
}
