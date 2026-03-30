/**
 * MSW server setup — reutilizable en todos los archivos de test.
 *
 * Importar en los tests que necesiten interceptar HTTP:
 *   import { server } from './mocks/server'
 *
 * Los lifecycle hooks (beforeAll/afterEach/afterAll) se configuran
 * en src/test/setup.js para que estén disponibles globalmente.
 */

import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
