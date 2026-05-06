import { helper } from './foo';

export class App {
    run(x: number): number {
        return helper(x) + 1;
    }
}

export function main() {
    return new App().run(3);
}
