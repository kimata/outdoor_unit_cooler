import React from "react";
import { ApiResponse } from "../lib/ApiResponse";
import { Loading } from "./common/Loading";
import { AnimatedNumber } from "./common/AnimatedNumber";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const CoolingMode = React.memo(({ isReady, stat }: Props) => {
    const dutyInfo = (mode: ApiResponse.Mode) => {
        return (
            <div className="container">
                <div className="row">
                    <div className="col-6">
                        <span className="me-1">On:</span>
                        <AnimatedNumber 
                            value={mode.duty.on_sec} 
                            decimals={0}
                            className="display-6 digit"
                        />
                        <span className="ms-1">sec</span>
                    </div>
                    <div className="col-6">
                        <span className="me-1">Off:</span>
                        <AnimatedNumber 
                            value={Math.round(mode.duty.off_sec / 60)} 
                            decimals={0}
                            className="display-6 digit"
                        />
                        <span className="ms-1">min</span>
                    </div>
                </div>
            </div>
        );
    };

    const modeInfo = (mode: ApiResponse.Mode) => {
        if (mode == null) {
            return <Loading size="large" />;
        }

        return (
            <div data-testid="cooling-info">
                <div className="display-1 align-middle ms-1">
                    <AnimatedNumber 
                        value={mode.mode_index} 
                        decimals={0}
                        className="fw-bold digit"
                    />
                </div>
                {dutyInfo(mode)}
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">現在の冷却モード</h4>
                    </div>
                    <div className="card-body">{isReady || stat.mode.mode_index !== 0 ? modeInfo(stat.mode) : <Loading size="large" />}</div>
                </div>
            </div>
        </div>
    );
});

CoolingMode.displayName = 'CoolingMode';

export { CoolingMode };
