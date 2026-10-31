const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../static/js/floating_actions.js'), 'utf8');

function emitter() {
    const handlers = {};
    return {
        handlers,
        addEventListener(type, listener) {
            (handlers[type] ||= []).push(listener);
        },
        emit(type, event) {
            for (const listener of handlers[type] || []) listener(event);
        },
    };
}

function classes(names) {
    const values = new Set(names);
    return {
        contains: (name) => values.has(name),
        toggle(name, forced) {
            if (forced === true) values.add(name);
            else if (forced === false) values.delete(name);
            else if (values.has(name)) values.delete(name);
            else values.add(name);
        },
    };
}

function harness() {
    const symbol = {textContent: '+'};
    const toggle = Object.assign(emitter(), {
        attrs: {'aria-label': 'Open guide actions', 'aria-expanded': 'false'},
        querySelector: () => symbol,
        getAttribute(name) { return this.attrs[name]; },
        setAttribute(name, value) { this.attrs[name] = value; },
        focus() { this.focused = true; },
    });
    const panel = {
        classList: classes(['wk-fab__panel']),
        attrs: {},
        inert: true,
        setAttribute(name, value) { this.attrs[name] = value; },
    };
    const root = Object.assign(emitter(), {
        dataset: {},
        querySelector(selector) {
            return selector === '[data-wk-fab-toggle]' ? toggle : panel;
        },
        contains(target) { return target === toggle || target === panel || target?.inside === true; },
        dispatchEvent(event) { this.emit(event.type, event); },
    });
    const doc = Object.assign(emitter(), {
        readyState: 'complete',
        querySelectorAll: () => [root],
    });
    class CustomEvent {
        constructor(type, options) { this.type = type; this.detail = options.detail; }
    }
    vm.runInNewContext(script, {document: doc, CustomEvent});

    const buttonClick = () => toggle.emit('click', {target: toggle, stopPropagation() {}});
    const action = (keepOpen = false) => ({
        closest(selector) {
            if (selector === '.wk-fab__item:not([data-wk-fab-keep-open])' && !keepOpen) return this;
            return null;
        },
    });
    return {root, toggle, panel, symbol, doc, buttonClick, action};
}

test('both Guide and price menus use the same collapsed and expanded states', () => {
    const ui = harness();
    assert.equal(ui.panel.classList.contains('is-open'), false);
    assert.equal(ui.panel.inert, true);
    assert.equal(ui.panel.attrs['aria-hidden'], 'true');
    assert.equal(ui.toggle.attrs['aria-expanded'], 'false');

    ui.buttonClick();
    assert.equal(ui.panel.classList.contains('is-open'), true);
    assert.equal(ui.panel.inert, false);
    assert.equal(ui.panel.attrs['aria-hidden'], 'false');
    assert.equal(ui.toggle.attrs['aria-expanded'], 'true');
    assert.equal(ui.toggle.attrs['aria-label'], 'Close guide actions');
    assert.equal(ui.symbol.textContent, '×');

    ui.buttonClick();
    assert.equal(ui.panel.classList.contains('is-open'), false);
    assert.equal(ui.symbol.textContent, '+');
    assert.equal(ui.toggle.attrs['aria-label'], 'Open guide actions');
});

test('action selection closes the panel, except for the inline rating tray', () => {
    const ui = harness();
    ui.buttonClick();
    ui.root.emit('click', {target: ui.action(true)});
    assert.equal(ui.panel.classList.contains('is-open'), true);

    ui.root.emit('click', {target: ui.action()});
    assert.equal(ui.panel.classList.contains('is-open'), false);
});

test('outside click and Escape close an open menu, with keyboard focus restored', () => {
    const ui = harness();
    ui.buttonClick();
    ui.doc.emit('click', {target: {inside: false}});
    assert.equal(ui.panel.classList.contains('is-open'), false);

    ui.buttonClick();
    ui.doc.emit('keydown', {key: 'Escape'});
    assert.equal(ui.panel.classList.contains('is-open'), false);
    assert.equal(ui.toggle.focused, true);
});

test('closing emits a state change that can hide the price rating tray', () => {
    const ui = harness();
    const events = [];
    ui.root.addEventListener('wk:fab:change', (event) => events.push(event.detail.open));
    ui.buttonClick();
    ui.buttonClick();
    assert.deepEqual(events, [true, false]);
});
