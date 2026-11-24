### PORTABLE

|이동에 필요한 근거|현재 관측|
|---|---|
|같은 PC / 게시 ref로 이동 / 미게시 WIP 복원|{{portability_mode}}|
|승인된 repo·ref·예상 SHA·base와 원격 read-back|{{portable_ref}}|
|이동 대상의 예상 SHA|{{portable_expected_sha}}|
|checkpoint ID / manifest SHA-256 / 필수·제외 경로|{{manifest}} / {{manifest_sha256}} / {{required_excluded}}|
|local_saved / portable_verified / restore_verified의 근거|{{portable_receipts}}|
|orphan commit / 원격 ref read-back / WIP unverified|{{portable_commit}} / {{portable_readback}} / {{portable_unverified}}|
|복원 Task·환경 재구성·다음 게이트|{{restored_task}}|

### RECOVERY

|중단·복구에 필요한 근거|현재 관측|
|---|---|
|정상/비정상 중단과 마지막 정상 체크포인트|{{interruption}}|
|마지막 실제 관측·확인하지 못한 실행|{{uncertain_execution}}|
|기존 소유권·정착 근거|{{settlement}}|
|허용된 기존 복구/재시도 절차와 상한|{{recovery_route}}|

### PARALLEL

|병렬 작업에 필요한 근거|현재 관측|
|---|---|
|Task·writer·branch/worktree·write scope|{{writers}}|
|공유 인터페이스·소유자|{{shared_interfaces}}|
|선행·의존 관계|{{parallel_dependencies}}|
|충돌·통합 순서와 결정권자|{{conflicts_and_order}}|

### ENVIRONMENT

|재현에 필요한 정보|확인한 조건|
|---|---|
|도구·버전·의존성|{{tool_versions}}|
|승인된 실행 경로·제약|{{runtime_constraints}}|
|재구성 방법·남은 환경 확인|{{reconstruction}}|
