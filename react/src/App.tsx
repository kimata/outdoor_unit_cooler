import { useState, useEffect } from "react";
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

import { ApiResponse } from "./lib/ApiResponse";

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

    const [isStatReady, setStatReady] = useState(false);
    const [isLogReady, setLogReady] = useState(false);
    const [stat, setStat] = useState<ApiResponse.Stat>(emptyStat);
    const [log, setLog] = useState<ApiResponse.Log>(emptyLog);
    const [updateTime, setUpdateTime] = useState("Unknown");
    const [error, setError] = useState(false);
    const buildDate = dayjs(preval`module.exports = new Date().toUTCString();`).format("LLL");
    const buildDateFrom = dayjs(preval`module.exports = new Date().toUTCString();`).fromNow();

    const fetchData = (url: string) => {
        return new Promise((resolve) => {
            fetch(url)
                .then((res) => res.json())
                .then((resJson) => resolve(resJson))
                .catch((e) => {
                    setError(true);
                    console.error("通信に失敗しました．", e);
                });
        });
    };

    const errorMessage = (message: string) => {
        return (
            <div className="row justify-content-center" data-testid="error">
                <div className="col-11 text-end">
                    <div className="alert alert-danger d-flex align-items-center" role="alert">
                        <div>{message}</div>
                    </div>
                </div>
            </div>
        );
    };

    const showError = (error: boolean) => {
        if (error) {
            return errorMessage("データの読み込みに失敗しました．");
        }
    };

    useEffect(() => {
        const loadStat = async () => {
            let res: ApiResponse.Stat = (await fetchData(API_ENDPOINT + "/stat")) as ApiResponse.Stat;
            setError(false);
            setStat(res);
            setStatReady(true);
            setUpdateTime(dayjs().format("LLL"));
        };

        const loadLog = async () => {
            let res: ApiResponse.Log = (await fetchData(API_ENDPOINT + "/log_view")) as ApiResponse.Log;
            setLog(res);
            setLogReady(true);
            setError(false);
            setUpdateTime(dayjs().format("llll"));
        };

        let eventSource: EventSource;
        const watchEvent = async () => {
            loadLog();
            eventSource = new EventSource(API_ENDPOINT + "/event");
            eventSource.addEventListener("message", (e) => {
                if (e.data === "log") {
                    loadLog();
                }
            });
            eventSource.onerror = () => {
                if (eventSource.readyState === 2) {
                    console.warn("EventSource が閉じられました．", e);
                    eventSource.close();
                    setTimeout(watchEvent, 1000);
                }
            };
        };

        loadStat();
        watchEvent();

        // NOTE: 更新日時表記が，「1分前」になる前に更新を終えれる
        // タイミングで規定する
        const intervalId = setInterval(() => {
            loadStat();
        }, 58000);

        return () => {
            clearInterval(intervalId);
            eventSource.close();
        };
    }, []);

    return (
        <>
            <div className="App">
                <div className="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
                    <h1 className="display-6 my-0 mr-md-auto font-weight-normal">室外機自動冷却システム</h1>
                </div>
                {showError(error)}
                <div>
                    <div className="container">
                        <div className="row display-flex row-cols-1 row-cols-lg-2 row-cols-xl-2 row-cols-xxl-3 g-3">
                            <Watering isReady={isStatReady} stat={stat} />
                            <History isReady={isStatReady} stat={stat} />
                            <CoolingMode isReady={isStatReady} stat={stat} />
                            <AirConditioner isReady={isStatReady} stat={stat} />
                            <Sensor isReady={isStatReady} stat={stat} />
                            <Log isReady={isLogReady} log={log} />
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
                                ビルド日時: {buildDate} [{buildDateFrom}]
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
