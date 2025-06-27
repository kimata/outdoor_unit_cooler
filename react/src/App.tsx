import { useState, useMemo, useCallback } from "react";
import "./App.css";

import "bootstrap/dist/css/bootstrap.min.css";
import { Github } from "react-bootstrap-icons";

import "dayjs/locale/ja";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import localizedFormat from "dayjs/plugin/localizedFormat";

dayjs.locale("ja");
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);

import preval from "preval.macro";
import { version as reactVersion } from "react";

import { ApiResponse } from "./lib/ApiResponse";
import { useApi } from "./hooks/useApi";
import { useEventSource } from "./hooks/useEventSource";
import { ErrorMessage } from "./components/common/ErrorMessage";

import { Watering } from "./components/Watering";
import { History } from "./components/History";
import { CoolingMode } from "./components/CoolingMode";
import { AirConditioner } from "./components/AirConditioner";
import { Sensor } from "./components/Sensor";
import { Log } from "./components/Log";

function App() {
    const API_ENDPOINT = "/unit_cooler/api";

    const emptyStat: ApiResponse.Stat = {
        cooler_status: {
            message: "",
            status: 0,
        },
        outdoor_status: {
            message: "",
            status: 0,
        },
        mode: {
            duty: {
                enable: false,
                off_sec: 0,
                on_sec: 0,
            },
            mode_index: 0,
            state: 0,
        },
        sensor: {
            temp: [],
            humi: [],
            lux: [],
            solar_rad: [],
            rain: [],
            power: [],
        },
        watering: [
            {
                amount: 0,
                price: 0,
            },
        ],
    };
    const emptyLog: ApiResponse.Log = {
        data: [],
        last_time: 0,
    };

    const emptySysInfo: ApiResponse.SysInfo = {
        date: "",
        image_build_date: "",
        load_average: "?",
        uptime: ""
    };

    const [updateTime, setUpdateTime] = useState("Unknown");
    const [isLogFirstLoad, setIsLogFirstLoad] = useState(true);

    // API calls using custom hooks
    const {
        data: stat,
        loading: statLoading,
        error: statError,
        refetch: refetchStat
    } = useApi(`${API_ENDPOINT}/stat`, emptyStat, { interval: 58000 });

    const {
        data: log,
        loading: logLoading,
        error: logError,
        refetch: refetchLog
    } = useApi(`${API_ENDPOINT}/proxy/json/api/log_view`, emptyLog);

    const {
        data: sysInfo,
        error: sysInfoError
    } = useApi(`${API_ENDPOINT}/sysinfo`, emptySysInfo, { interval: 58000 });

    const {
        data: actuatorSysInfo,
        error: actuatorSysInfoError
    } = useApi(`${API_ENDPOINT}/actuator_sysinfo`, emptySysInfo, { interval: 58000 });

    // EventSource for real-time updates
    useEventSource(`${API_ENDPOINT}/proxy/event/api/event`, {
        onMessage: (e) => {
            if (e.data === "log") {
                refetchLog();
                refetchStat();
                setUpdateTime(dayjs().format("llll"));
            }
        }
    });

    // Update isLogFirstLoad when logLoading changes
    if (!logLoading && isLogFirstLoad) {
        setIsLogFirstLoad(false);
    }

    // Update time when stat data changes
    if (!statLoading && stat && updateTime === "Unknown") {
        setUpdateTime(dayjs().format("LLL"));
    }

    const hasError = statError || logError || sysInfoError || actuatorSysInfoError;
    const isReady = !statLoading && !logLoading;

    const getErrorMessage = () => {
        if (statError) return `統計データ: ${statError}`;
        if (logError) return `ログデータ: ${logError}`;
        if (sysInfoError) return `システム情報: ${sysInfoError}`;
        if (actuatorSysInfoError) return `アクチュエータ情報: ${actuatorSysInfoError}`;
        return "データの読み込みに失敗しました";
    };

    const handleRetry = useCallback(() => {
        refetchStat();
        refetchLog();
    }, [refetchStat, refetchLog]);

    // Format system info data with memoization
    const systemInfoMemo = useMemo(() => ({
        imageBuildDate: sysInfo?.image_build_date ? dayjs(sysInfo.image_build_date).format("LLL") : "?",
        imageBuildDateFrom: sysInfo?.image_build_date ? dayjs(sysInfo.image_build_date).fromNow() : "?",
        actuatorUptime: actuatorSysInfo?.uptime ? dayjs(actuatorSysInfo.uptime).format("LLL") : "?",
        actuatorUptimeFrom: actuatorSysInfo?.uptime ? dayjs(actuatorSysInfo.uptime).fromNow() : "?",
        actuatorLoadAverage: actuatorSysInfo?.load_average || "?"
    }), [sysInfo?.image_build_date, actuatorSysInfo?.uptime, actuatorSysInfo?.load_average]);

    const buildInfo = useMemo(() => ({
        buildDate: dayjs(preval`module.exports = new Date().toUTCString();`).format("LLL"),
        buildDateFrom: dayjs(preval`module.exports = new Date().toUTCString();`).fromNow()
    }), []);


    return (
        <>
            <div className="App">
                <div className="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
                    <h1 className="display-6 my-0 mr-md-auto font-weight-normal">室外機自動冷却システム</h1>
                </div>
                {hasError && (
                    <ErrorMessage
                        message={getErrorMessage()}
                        onRetry={handleRetry}
                    />
                )}
                <div>
                    <div className="container">
                        <div className="row display-flex row-cols-1 row-cols-lg-2 row-cols-xl-2 row-cols-xxl-3 g-3">
                            <Watering isReady={isReady} stat={stat} />
                            <History isReady={isReady} stat={stat} />
                            <CoolingMode isReady={isReady} stat={stat} />
                            <AirConditioner isReady={isReady} stat={stat} />
                            <Sensor isReady={isReady} stat={stat} />
                            <Log isReady={!logLoading || !isLogFirstLoad} log={log} />
                        </div>
                    </div>
                </div>
                <div className="p-1 float-end text-end m-2 mt-4">
                    <small>
                        <p className="text-muted m-0">
                            <small>更新日時: {updateTime}</small>
                        </p>
                        <p className="text-muted m-0">
                            <small>
                                アクチュエータ起動時刻: {systemInfoMemo.actuatorUptime} [{systemInfoMemo.actuatorUptimeFrom}]
                            </small>
                        </p>
                        <p className="text-muted m-0">
                            <small>
                                アクチュエータ load average: {systemInfoMemo.actuatorLoadAverage}
                            </small>
                        </p>
                        <p className="text-muted m-0">
                            <small>
                                イメージビルド: {systemInfoMemo.imageBuildDate} [{systemInfoMemo.imageBuildDateFrom}]
                            </small>
                        </p>
                        <p className="text-muted m-0">
                            <small>
                                React ビルド: {buildInfo.buildDate} [{buildInfo.buildDateFrom}]
                            </small>
                        </p>
                        <p className="text-muted m-0">
                            <small>
                                React バージョン: {reactVersion}
                            </small>
                        </p>
                        <p className="display-6">
                            <a
                                href="https://github.com/kimata/outdoor_unit_cooler"
                                className="text-secondary"
                            >
                                <Github />
                            </a>
                        </p>
                    </small>
                </div>
            </div>
        </>
    );
}

export default App;
