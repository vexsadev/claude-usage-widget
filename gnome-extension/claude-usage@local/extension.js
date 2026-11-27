// Claude Usage — colored 5-hour / weekly limit pills in the GNOME top bar.
// Reads rate_limits.json (written by the Claude Code status line hook) from the data folder the
// installer stamps into metadata.json, default $XDG_DATA_HOME/claude-usage-widget.
// Green < 80%, yellow 80–89%, red >= 90%, warning sign at >= 95%.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const WIDGET_BIN = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'claude-usage-widget']);
const LIMITS = [
    {key: 'five_hour', short: '5h', name: '5-hour'},
    {key: 'seven_day', short: 'wk', name: 'Weekly'},
];
const COLORS = ['claude-green', 'claude-yellow', 'claude-red', 'claude-grey'];

function fmtDur(sec) {
    sec = Math.max(0, Math.floor(sec));
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
    return `${m}m`;
}

function colorFor(pct) {
    if (pct === null) return 'claude-grey';
    if (pct >= 90) return 'claude-red';
    if (pct >= 80) return 'claude-yellow';
    return 'claude-green';
}

function readLimits(rateFile) {
    try {
        const [ok, bytes] = GLib.file_get_contents(rateFile);
        if (!ok) return null;
        const d = JSON.parse(new TextDecoder().decode(bytes));
        return d.rate_limits || null;
    } catch (e) {
        return null;
    }
}

function spawn(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
        return true;
    } catch (e) {
        return false;
    }
}

export default class ClaudeUsageExtension extends Extension {
    enable() {
        // the installer stamps "data-dir" into metadata.json (it may be a custom CLAUDE_USAGE_WIDGET_HOME)
        const dataDir = this.metadata['data-dir'] ||
            GLib.build_filenamev([GLib.get_user_data_dir(), 'claude-usage-widget']);
        this._rateFile = GLib.build_filenamev([dataDir, 'rate_limits.json']);
        this._button = new PanelMenu.Button(0.5, 'Claude Usage', false);
        const box = new St.BoxLayout({style_class: 'claude-usage-box'});
        this._pills = {};
        for (const l of LIMITS) {
            const pill = new St.Label({
                text: `– ${l.short}`,
                style_class: 'claude-pill claude-grey',
                y_align: Clutter.ActorAlign.CENTER,
            });
            box.add_child(pill);
            this._pills[l.key] = pill;
        }
        this._button.add_child(box);

        const toggle = new PopupMenu.PopupMenuItem('Show / hide widget');
        toggle.connect('activate', () => {
            // toggles the running widget (starts it if it is not running)
            spawn([WIDGET_BIN, '--toggle']);
        });
        this._button.menu.addMenuItem(toggle);
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._info = {};
        for (const l of LIMITS) {
            const it = new PopupMenu.PopupMenuItem(`${l.name}: –`, {reactive: false});
            this._button.menu.addMenuItem(it);
            this._info[l.key] = it;
        }
        this._updated = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._button.menu.addMenuItem(this._updated);

        Main.panel.addToStatusArea(this.uuid, this._button, 0, 'right');
        this._update();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _update() {
        const rl = readLimits(this._rateFile) || {};
        const now = Date.now() / 1000;
        for (const l of LIMITS) {
            const v = rl[l.key];
            let pct = null;
            let reset = null;
            if (v && typeof v.used_percentage === 'number') {
                pct = v.used_percentage;
                reset = typeof v.resets_at === 'number' ? v.resets_at
                    : (v.resets_at ? Date.parse(v.resets_at) / 1000 : null);
                if (reset && now >= reset) {
                    pct = 0;  // window rolled over since the last capture
                    reset = null;
                }
            }
            const pill = this._pills[l.key];
            for (const c of COLORS) pill.remove_style_class_name(c);
            pill.add_style_class_name(colorFor(pct));
            const warn = pct !== null && pct >= 95 ? '⚠ ' : '';
            const pctTxt = pct === null ? '–' : `${Math.round(pct)}%`;
            const resetTxt = reset ? ` · ${fmtDur(reset - now)}` : '';
            pill.text = `${warn}${pctTxt} ${l.short}${resetTxt}`;
            this._info[l.key].label.text = pct === null ? `${l.name}: waiting for Claude Code`
                : `${l.name}: ${Math.round(pct)}% used` + (reset ? ` · resets in ${fmtDur(reset - now)}` : '');
        }
        try {
            const info = Gio.File.new_for_path(this._rateFile).query_info('time::modified', 0, null);
            const age = now - info.get_modification_date_time().to_unix();
            this._updated.label.text = age < 60 ? 'Updated just now' : `Updated ${fmtDur(age)} ago`;
        } catch (e) {
            this._updated.label.text = 'No data yet';
        }
    }

    disable() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = null;
        }
        this._button?.destroy();
        this._button = null;
        this._pills = null;
        this._info = null;
        this._updated = null;
    }
}
