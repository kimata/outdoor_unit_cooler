import { ApiResponse } from '../lib/ApiResponse'

type Props = {
    isReady: boolean,
    stat: ApiResponse.Stat
}

const CoolingMode = ({ isReady, stat }: Props) => {
    const dutyInfo = (mode: ApiResponse.Mode) => {
        return (
            <div className="container">
                <div className="row">
                    <div className="col-6">
                        <span className="me-1">On:</span>
                        <span className="display-6 digit">{mode.duty.on_sec}</span>
                        <span className="ms-1">sec</span>
                    </div>
                    <div className="col-6">
                        <span className="me-1">Off:</span>
                        <span className="display-6 digit">{Math.round(mode.duty.off_sec / 60)}</span>
                        <span className="ms-1">min</span>
                    </div>
                </div>
            </div>
        );
    };

    const modeInfo = (mode: ApiResponse.Mode) => {
        if (mode == null) {
            return loading();
        }

        return (
            <div data-testid="cooling-info">
                <div className="display-1 align-middle ms-1">
                    <span className="fw-bold digit">{mode.mode_index}</span>
                </div>
                {dutyInfo(mode)}
            </div>
        );
    };
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">現在の冷却モード</h4>
                    </div>
                    <div className="card-body">{isReady ? modeInfo(stat.mode) : loading()}</div>
                </div>
            </div>
        </div>
    );
};

export { CoolingMode };
