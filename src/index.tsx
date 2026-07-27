import {
  definePlugin,
  ToggleField,
  PanelSection,
  PanelSectionRow,
  DropdownItem,
  ServerAPI,
  staticClasses,
} from "decky-frontend-lib";
import { VFC } from "react";
import { useEffect, useState } from 'react'
import { GiNightSleep } from "react-icons/gi";
import i18n from './i18n'

let backendRunning = false;
let showNotify     = false;
let language = i18n.getCurrentLanguage()
const t = i18n.useTranslations(language)

const RUN_ON_LOGIN = "run_on_login"
const SHOW_NOTIFY  = "show_notify"
const BATTERY_IDLE_MINUTES = "battery_idle_minutes"
const AC_IDLE_MINUTES = "ac_idle_minutes"
const BATTERY_SUSPEND_MINUTES = "battery_suspend_minutes"
const AC_SUSPEND_MINUTES = "ac_suspend_minutes"

const DEFAULT_BATTERY_IDLE_MINUTES = 5
const DEFAULT_AC_IDLE_MINUTES = 5
const DEFAULT_BATTERY_SUSPEND_MINUTES = 10
const DEFAULT_AC_SUSPEND_MINUTES = 10

const minutesToSeconds = (minutes: number) => minutes * 60
const TIMEOUT_PRESET_MINUTES = [0, 1, 5, 15, 30, 60] as const
const formatTimeoutMinutes = (minutes: number) => {
  if (minutes === 0) return "Disabled"
  if (minutes === 60) return "1 hour"
  return `${minutes} minutes`
}
const timeoutDropdownOptions = TIMEOUT_PRESET_MINUTES.map((minutes) => ({
  data: minutes,
  label: formatTimeoutMinutes(minutes),
}))

interface TimeoutDropdownProps {
  label: string
  value: number
  onChange: (minutes: number) => Promise<void>
}

const TimeoutDropdown: VFC<TimeoutDropdownProps> = ({ label, value, onChange }) => {
  return (
    <PanelSectionRow>
      <DropdownItem
        label={label}
        menuLabel={label}
        rgOptions={timeoutDropdownOptions as any}
        selectedOption={value}
        focusable
        onChange={(option: { data: number }) => {
          void onChange(option.data)
        }}
      />
    </PanelSectionRow>
  )
}

const Content: VFC<{ serverApi: ServerAPI }> = ({serverApi}) => {
  const [running, setRunning] = useState<boolean>(backendRunning);
  const [notify, setNotify] = useState<boolean>(showNotify);
  const [batteryIdleMinutes, setBatteryIdleMinutes] = useState<number>(DEFAULT_BATTERY_IDLE_MINUTES);
  const [acIdleMinutes, setAcIdleMinutes] = useState<number>(DEFAULT_AC_IDLE_MINUTES);
  const [batterySuspendMinutes, setBatterySuspendMinutes] = useState<number>(DEFAULT_BATTERY_SUSPEND_MINUTES);
  const [acSuspendMinutes, setAcSuspendMinutes] = useState<number>(DEFAULT_AC_SUSPEND_MINUTES);

  const startBackend = async () => {
    const result = await serverApi.callPluginMethod<any, any>("start_backend", {});
    return result;
  }

  const stopBackend = async () => {
    return await serverApi.callPluginMethod<any, any>("stop_backend", {});
  }

  const setSettings = async (key: string, value: any) => {
    return await serverApi.callPluginMethod<any, any>("set_settings", {key: key, value: value});
  }

  useEffect(() => {
    const loadSettings = async () => {
      const batteryIdle = await serverApi.callPluginMethod<any, any>("get_settings", {
        key: BATTERY_IDLE_MINUTES,
        defaults: DEFAULT_BATTERY_IDLE_MINUTES,
      });
      if (batteryIdle.success) {
        setBatteryIdleMinutes(batteryIdle.result);
      }

      const acIdle = await serverApi.callPluginMethod<any, any>("get_settings", {
        key: AC_IDLE_MINUTES,
        defaults: DEFAULT_AC_IDLE_MINUTES,
      });
      if (acIdle.success) {
        setAcIdleMinutes(acIdle.result);
      }

      const batterySuspend = await serverApi.callPluginMethod<any, any>("get_settings", {
        key: BATTERY_SUSPEND_MINUTES,
        defaults: DEFAULT_BATTERY_SUSPEND_MINUTES,
      });
      if (batterySuspend.success) {
        setBatterySuspendMinutes(batterySuspend.result);
      }

      const acSuspend = await serverApi.callPluginMethod<any, any>("get_settings", {
        key: AC_SUSPEND_MINUTES,
        defaults: DEFAULT_AC_SUSPEND_MINUTES,
      });
      if (acSuspend.success) {
        setAcSuspendMinutes(acSuspend.result);
      }
    };

    loadSettings();
  }, [serverApi]);

  return (
    <PanelSection title={t('Settings')}>
      <PanelSectionRow>
      <ToggleField
          label={t('Background Monitor')}
          onChange={async (checked) => {
            setRunning(checked)
            backendRunning = checked
            await setSettings(RUN_ON_LOGIN, checked)
            checked ? await startBackend() : await stopBackend() 
          }}
          checked={running}
          />
      <label>{t('bg_tip')}</label>
      </PanelSectionRow>
      <PanelSectionRow>
      <ToggleField
          label={t('Show Notify')}
          onChange={async (checked) => {
            setNotify(checked)
            showNotify = checked
            await setSettings(SHOW_NOTIFY, checked)
          }}
          checked={notify}
          />
      <label>{t('notify_tip')}</label>
      </PanelSectionRow>
      <TimeoutDropdown
        label="On battery power, dim after"
        value={batteryIdleMinutes}
        onChange={async (minutes) => {
          setBatteryIdleMinutes(minutes)
          await setSettings(BATTERY_IDLE_MINUTES, minutes)
        }}
      />
      <TimeoutDropdown
        label="When plugged in, dim after"
        value={acIdleMinutes}
        onChange={async (minutes) => {
          setAcIdleMinutes(minutes)
          await setSettings(AC_IDLE_MINUTES, minutes)
        }}
      />
      <TimeoutDropdown
        label="On battery power, sleep after"
        value={batterySuspendMinutes}
        onChange={async (minutes) => {
          setBatterySuspendMinutes(minutes)
          await setSettings(BATTERY_SUSPEND_MINUTES, minutes)
        }}
      />
      <TimeoutDropdown
        label="When plugged in, sleep after"
        value={acSuspendMinutes}
        onChange={async (minutes) => {
          setAcSuspendMinutes(minutes)
          await setSettings(AC_SUSPEND_MINUTES, minutes)
        }}
      />
    </PanelSection>
  );
};

export default definePlugin((serverApi: ServerAPI) => {
  let SettingDef = {
    battery_idle: {
      field: 1,
      wireType: 5
    },
    ac_idle: {
      field: 2,
      wireType: 5
    },
    battery_suspend: {
      field: 3,
      wireType: 5
    },
    ac_suspend: {
      field: 4,
      wireType: 5
    },
  }

  const _updateSettings = async (data: string) => {
    await SteamClient.System.UpdateSettings(window.btoa(data))
  }
  let updateIdleSetting = _updateSettings;
  let updateSuspendSetting = _updateSettings;

  // SteamClient023 does not have `RegisterForOnSuspendRequest`
  if (!SteamClient.System.RegisterForOnSuspendRequest) {
    // SteamClient023 using new suspend settings
    SettingDef.battery_suspend = {
      field: 24003,
      wireType: 0
    }
    SettingDef.ac_suspend = {
      field: 24004,
      wireType: 0
    }
    updateSuspendSetting = async (data: string) => {
      await SteamClient.Settings.SetSetting(window.btoa(data))
    };
  }

  /**
   * Protobuf setting generation
   * @param field 1:battery_idle; 2:ac_idle; 3/24003:battery_suspend; 4/24004:ac_suspend
   * @param value 0 for disable (seconds)
   * @param wireType 0 for int32, 5 for float
   * @returns settings in binary string
   */
  function genSettings(field: any, value: number) {
    const buf = [];
    
    let key = (field.field << 3) | field.wireType;
    do {
      let b = key & 0x7F;
      key >>>= 7;
      if (key) b |= 0x80;
      buf.push(b);
    } while (key);

    if (field.wireType === 0) {
      do {
        let b = value & 0x7F;
        value >>>= 7;
        if (value) b |= 0x80;
        buf.push(b);
      } while (value);
      return String.fromCharCode(...buf);
    } else if (field.wireType === 5) {
      const valueBytes = new Uint8Array(new Float32Array([value]).buffer);
      return String.fromCharCode(...buf, ...valueBytes);
    } else {
      throw new Error('Unsupported wire type');
    }
  }

  async function updateSetting(battery_idle: number, ac_idle: number, battery_suspend: number, ac_suspend: number) {
    let _battery_idle = genSettings(SettingDef.battery_idle, battery_idle);
    let _ac_idle = genSettings(SettingDef.ac_idle, ac_idle);
    let _battery_suspend = genSettings(SettingDef.battery_suspend, battery_suspend);
    let _ac_suspend = genSettings(SettingDef.ac_suspend, ac_suspend);
    await updateIdleSetting(_battery_idle+_ac_idle);
    await updateSuspendSetting(_battery_suspend+_ac_suspend);
  }

  const applySavedSettings = async () => {
    const batteryIdle = await getSettings(BATTERY_IDLE_MINUTES, DEFAULT_BATTERY_IDLE_MINUTES)
    const acIdle = await getSettings(AC_IDLE_MINUTES, DEFAULT_AC_IDLE_MINUTES)
    const batterySuspend = await getSettings(BATTERY_SUSPEND_MINUTES, DEFAULT_BATTERY_SUSPEND_MINUTES)
    const acSuspend = await getSettings(AC_SUSPEND_MINUTES, DEFAULT_AC_SUSPEND_MINUTES)

    const batteryIdleSeconds = minutesToSeconds(batteryIdle.success ? batteryIdle.result : DEFAULT_BATTERY_IDLE_MINUTES)
    const acIdleSeconds = minutesToSeconds(acIdle.success ? acIdle.result : DEFAULT_AC_IDLE_MINUTES)
    const batterySuspendSeconds = minutesToSeconds(batterySuspend.success ? batterySuspend.result : DEFAULT_BATTERY_SUSPEND_MINUTES)
    const acSuspendSeconds = minutesToSeconds(acSuspend.success ? acSuspend.result : DEFAULT_AC_SUSPEND_MINUTES)

    await updateSetting(batteryIdleSeconds, acIdleSeconds, batterySuspendSeconds, acSuspendSeconds)
  }
  
  const getEvent = async () => {
    return await serverApi.callPluginMethod<any, any>("get_event", {});
  }

  const getSettings = async (key: string, defaults: any) => {
    return await serverApi.callPluginMethod<any, any>("get_settings", {key: key, defaults: defaults});
  }

  const startBackend = async () => {
    const result = await serverApi.callPluginMethod<any, any>("start_backend", {});
    return result;
  }

  let timeout:NodeJS.Timeout;
  const notify = (title: string, body: string) => {
    if (!showNotify) return
    clearTimeout(timeout)
    timeout = setTimeout(()=>{
      serverApi.toaster.toast({
        title: title,
        body: body,
        duration: 1_500,
        sound: 1,
        icon: <GiNightSleep />,
      });
    }, 2000)
  }

  let interval = setInterval(async () => {
    let data = await getEvent();
    if(!data.success) return;
    let event = data.result;
    for (let e of event) {
      if (e.type == 'Inhibit') {
        notify(t("ScreenSaver"), t("Inhibit"))
        await updateSetting(0, 0, 0, 0);
      } else if (e.type == 'UnInhibit') {
        notify(t("ScreenSaver"), t("UnInhibit"))
        await applySavedSettings();
      }
    }
  }, 1000)

  setTimeout(async () => {
    let notify = await getSettings(SHOW_NOTIFY, false)
    if (notify.success) {
      showNotify = notify.result
    }

    let run = await getSettings(RUN_ON_LOGIN, true)
    if (run.success && run.result) {
      backendRunning = true
      await startBackend()
    }
  }, 0);

  return {
    title: <div className={staticClasses.Title}>Suspend Manager</div>,
    content: <Content serverApi={serverApi} />,
    icon: <GiNightSleep />,
    onDismount() {
      if (interval) clearInterval(interval);
      setTimeout(async () => {
        await applySavedSettings();
      }, 0);
    },
  };
});
